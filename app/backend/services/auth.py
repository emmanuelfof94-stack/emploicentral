import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from core.auth import create_access_token
from core.config import settings
from core.database import db_manager
from models.auth import OIDCState, PasswordResetToken, User
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _is_admin_email(email: str) -> bool:
    """True si l'email correspond à ADMIN_USER_EMAIL (compte propriétaire)."""
    admin_email = (getattr(settings, "admin_user_email", "") or "").strip().lower()
    return bool(admin_email) and (email or "").strip().lower() == admin_email


# ---- Politique de mot de passe ----
PASSWORD_MIN_LENGTH = max(8, int(os.environ.get("PASSWORD_MIN_LENGTH", 8)))

# Petite liste de mots de passe trop courants (FR + EN) à refuser d'emblée.
_COMMON_PASSWORDS = {
    "password", "motdepasse", "azerty", "azertyuiop", "qwerty", "qwertyuiop",
    "123456", "1234567", "12345678", "123456789", "1234567890", "000000",
    "111111", "abc123", "azerty123", "password1", "passw0rd", "motdepasse1",
    "iloveyou", "admin", "administrateur", "bonjour", "soleil", "loulou",
    "doudou", "chouchou", "12345", "00000000", "11111111", "aaaaaaaa",
}


def validate_password_strength(password: str, email: Optional[str] = None) -> None:
    """Valide la robustesse d'un mot de passe. Lève ValueError (→ 400) si trop faible."""
    pwd = password or ""
    if len(pwd) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères")
    low = pwd.strip().lower()
    if low in _COMMON_PASSWORDS:
        raise ValueError("Ce mot de passe est trop courant, choisissez-en un autre")
    if email:
        local = email.split("@", 1)[0].strip().lower()
        if low == email.strip().lower() or (len(local) >= 3 and low == local):
            raise ValueError("Le mot de passe ne doit pas être identique à votre email")


# ---- Local password hashing (stdlib PBKDF2-HMAC-SHA256) ----
_PBKDF2_ROUNDS = 240_000


def hash_password(password: str) -> str:
    """Hash a password with a random salt. Format: pbkdf2_sha256$rounds$salt_hex$hash_hex."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash, constant-time."""
    if not stored:
        return False
    try:
        algo, rounds_s, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(dk, expected)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_user(self, platform_sub: str, email: str, name: Optional[str] = None) -> User:
        """Get existing user or create new one."""
        start_time = time.time()
        logger.debug(f"[DB_OP] Starting get_or_create_user - platform_sub: {platform_sub}")
        # Try to find existing user
        result = await self.db.execute(select(User).where(User.id == platform_sub))
        user = result.scalar_one_or_none()
        logger.debug(f"[DB_OP] User lookup completed in {time.time() - start_time:.4f}s - found: {user is not None}")

        if user:
            # Update user info if needed
            user.email = email
            user.name = name
            user.last_login = datetime.now(timezone.utc)
        else:
            # Create new user
            user = User(id=platform_sub, email=email, name=name, last_login=datetime.now(timezone.utc))
            self.db.add(user)

        start_time_commit = time.time()
        logger.debug("[DB_OP] Starting user commit/refresh")
        await self.db.commit()
        await self.db.refresh(user)
        logger.debug(f"[DB_OP] User commit/refresh completed in {time.time() - start_time_commit:.4f}s")
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Find a user by email (case-insensitive)."""
        normalized = email.strip().lower()
        result = await self.db.execute(select(User).where(func.lower(User.email) == normalized))
        return result.scalar_one_or_none()

    async def register_local_user(self, email: str, password: str, name: Optional[str] = None) -> User:
        """Create a new local (email/password) user. Raises ValueError if email already exists."""
        normalized_email = email.strip().lower()
        validate_password_strength(password, normalized_email)
        existing = await self.get_user_by_email(normalized_email)
        if existing:
            raise ValueError("Un compte existe déjà avec cet email")

        user = User(
            id=f"local:{secrets.token_hex(12)}",
            email=normalized_email,
            name=name or normalized_email.split("@", 1)[0],
            role="admin" if _is_admin_email(normalized_email) else "user",
            password_hash=hash_password(password),
            last_login=datetime.now(timezone.utc),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("[register_local_user] Created local user %s", user.id)
        return user

    async def authenticate_local_user(self, email: str, password: str) -> Optional[User]:
        """Verify email/password credentials. Returns the user on success, else None."""
        user = await self.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            return None
        # Promotion du compte propriétaire en admin (si configuré via ADMIN_USER_EMAIL).
        if _is_admin_email(user.email) and user.role != "admin":
            user.role = "admin"
        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(self, user_id: str, current_password: str, new_password: str) -> None:
        """Change the password of a local account after verifying the current one.

        Raises ValueError (mapped to 400 by the router) on any failure: unknown user,
        account without a local password (OIDC-only), or wrong current password.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Compte introuvable")
        if not user.password_hash:
            raise ValueError("Ce compte n'a pas de mot de passe local")
        if not verify_password(current_password, user.password_hash):
            raise ValueError("Mot de passe actuel incorrect")
        validate_password_strength(new_password, user.email)
        if verify_password(new_password, user.password_hash):
            raise ValueError("Le nouveau mot de passe doit être différent de l'ancien")
        uid = user.id  # capturé avant commit (l'attribut ORM expire après)
        user.password_hash = hash_password(new_password)
        await self.db.commit()
        logger.info("[change_password] Password updated for user %s", uid)

    async def create_password_reset(self, email: str) -> Optional[Tuple[str, "User"]]:
        """Crée un jeton de réinitialisation pour un compte LOCAL existant.

        Retourne (jeton_brut, user) si un compte local existe pour cet email, sinon
        None (le routeur répond malgré tout 200 pour ne pas révéler l'existence du
        compte). Le jeton brut n'est connu qu'ici : seul son hash est stocké.
        """
        user = await self.get_user_by_email(email)
        if not user or not user.password_hash:
            return None  # compte inexistant ou sans mot de passe local (OIDC)

        # Purge des jetons expirés.
        await self.db.execute(
            delete(PasswordResetToken).where(PasswordResetToken.expires_at < datetime.now(timezone.utc))
        )
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        try:
            ttl = int(os.environ.get("PASSWORD_RESET_TTL_MINUTES", 60))
        except (TypeError, ValueError):
            ttl = 60
        row = PasswordResetToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl),
            used=0,
        )
        self.db.add(row)
        await self.db.commit()
        logger.info("[create_password_reset] Reset token issued for user %s", user.id)
        return raw_token, user

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        """Réinitialise le mot de passe à partir d'un jeton. Lève ValueError si invalide."""
        token_hash = hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()
        result = await self.db.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        row = result.scalar_one_or_none()
        if not row or row.used or row.expires_at < datetime.now(timezone.utc):
            raise ValueError("Lien de réinitialisation invalide ou expiré")

        user_result = await self.db.execute(select(User).where(User.id == row.user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Compte introuvable")
        validate_password_strength(new_password, user.email)
        user.password_hash = hash_password(new_password)
        row.used = 1
        await self.db.commit()
        logger.info("[reset_password] Password reset for user %s", row.user_id)

    async def issue_app_token(
        self,
        user: User,
        remember: bool = False,
    ) -> Tuple[str, datetime, Dict[str, Any]]:
        """Generate application JWT token for the authenticated user.

        `remember=True` émet un jeton longue durée (« rester connecté »), sinon la
        durée par défaut (JWT_EXPIRE_MINUTES).
        """
        if remember:
            try:
                expires_minutes = int(os.environ.get("REMEMBER_ME_MINUTES", 43200))  # 30 jours
            except (TypeError, ValueError):
                expires_minutes = 43200
        else:
            try:
                expires_minutes = int(getattr(settings, "jwt_expire_minutes", 60))
            except (TypeError, ValueError):
                logger.warning("Invalid JWT_EXPIRE_MINUTES value; fallback to 60 minutes")
                expires_minutes = 60
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)

        claims: Dict[str, Any] = {
            "sub": user.id,
            "email": user.email,
            "role": user.role,
        }

        if user.name:
            claims["name"] = user.name
        if user.last_login:
            claims["last_login"] = user.last_login.isoformat()
        token = create_access_token(claims, expires_minutes=expires_minutes)

        return token, expires_at, claims

    async def store_oidc_state(self, state: str, nonce: str, code_verifier: str):
        """Store OIDC state in database."""
        # Clean up expired states first
        await self.db.execute(delete(OIDCState).where(OIDCState.expires_at < datetime.now(timezone.utc)))

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)  # 10 minute expiry

        oidc_state = OIDCState(state=state, nonce=nonce, code_verifier=code_verifier, expires_at=expires_at)

        self.db.add(oidc_state)
        await self.db.commit()

    async def get_and_delete_oidc_state(self, state: str) -> Optional[dict]:
        """Get and delete OIDC state from database."""
        # Clean up expired states first
        await self.db.execute(delete(OIDCState).where(OIDCState.expires_at < datetime.now(timezone.utc)))

        # Find and validate state
        result = await self.db.execute(select(OIDCState).where(OIDCState.state == state))
        oidc_state = result.scalar_one_or_none()

        if not oidc_state:
            return None

        # Extract data before deleting
        state_data = {"nonce": oidc_state.nonce, "code_verifier": oidc_state.code_verifier}

        # Delete the used state (one-time use)
        await self.db.delete(oidc_state)
        await self.db.commit()

        return state_data


async def initialize_admin_user():
    """Initialize admin user if not exists"""
    if "MGX_IGNORE_INIT_ADMIN" in os.environ:
        logger.info("Ignore initialize admin")
        return

    from services.database import initialize_database

    # Ensure database is initialized first
    await initialize_database()

    admin_user_id = getattr(settings, "admin_user_id", "")
    admin_user_email = getattr(settings, "admin_user_email", "")

    if not admin_user_id or not admin_user_email:
        logger.warning("Admin user ID or email not configured, skipping admin initialization")
        return

    async with db_manager.async_session_maker() as db:
        # Check if admin user already exists
        result = await db.execute(select(User).where(User.id == admin_user_id))
        user = result.scalar_one_or_none()

        if user:
            # Update existing user to admin if not already
            if user.role != "admin":
                user.role = "admin"
                user.email = admin_user_email  # Update email too
                await db.commit()
                logger.debug(f"Updated user {admin_user_id} to admin role")
            else:
                logger.debug(f"Admin user {admin_user_id} already exists")
        else:
            # Create new admin user
            admin_user = User(id=admin_user_id, email=admin_user_email, role="admin")
            db.add(admin_user)
            await db.commit()
            logger.debug(f"Created admin user: {admin_user_id} with email: {admin_user_email}")
