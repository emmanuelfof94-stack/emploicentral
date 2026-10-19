"""Fixtures communes de la suite de tests backend.

Principes :
- Base SQLite TEMPORAIRE (jamais `app/backend/app.db`), recréée à vide pour chaque test.
- Aucune intégration externe : SMTP / WhatsApp / IA / Sentry / agrégateur sont
  neutralisés par variables d'environnement AVANT l'import de l'application, et
  toute connexion réseau sortante est bloquée (garde-fou sur `socket.connect`).
- Le `lifespan` de l'app n'est PAS exécuté (pas de seed mock, pas de scheduler) :
  la fixture initialise elle-même le moteur et les tables.
"""
from __future__ import annotations

import asyncio
import os
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = tempfile.mkdtemp(prefix="emploicentral-tests-")
TEST_DB_PATH = os.path.join(_TMP_DIR, "test.db")

# --- Environnement de test (doit précéder tout import de l'app) -------------
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DB_PATH}",
        "JWT_SECRET_KEY": "test-secret-key-not-for-production",
        "JWT_ALGORITHM": "HS256",
        "JWT_EXPIRE_MINUTES": "60",
        "ENVIRONMENT": "test",
        "DEBUG": "false",
        "AGGREGATOR_ENABLED": "false",
        "AGGREGATOR_RUN_ON_STARTUP": "false",
        "MGX_IGNORE_INIT_DATA": "1",
        "MGX_IGNORE_INIT_ADMIN": "1",
        "ADMIN_USER_EMAIL": "admin@emploi-tests.ci",
    }
)
for _var in (
    "SENTRY_DSN",
    "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM",
    "META_WA_TOKEN", "META_WA_PHONE_ID",
    "APP_AI_BASE_URL", "APP_AI_KEY",
    "OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET",
    "TRAINING_QUOTA_ENABLED",
    "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT",
    "PUBLIC_SITE_URL",
):
    os.environ.pop(_var, None)

import httpx  # noqa: E402

from core.auth import create_access_token  # noqa: E402
from core.database import Base, db_manager  # noqa: E402
from main import app  # noqa: E402  (importe aussi tous les modèles via les routers)
from services import rate_limit  # noqa: E402


# --------------------------------------------------------------------------- #
# Garde-fou : aucune connexion réseau sortante pendant les tests
# --------------------------------------------------------------------------- #
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _guarded(real):
    def _connect(self, address, *args, **kwargs):
        if self.family == getattr(socket, "AF_UNIX", None):
            return real(self, address, *args, **kwargs)
        raise RuntimeError(f"Connexion réseau interdite pendant les tests : {address!r}")

    return _connect


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded(_real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded(_real_connect_ex))
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit._failures.clear()
    yield
    rate_limit._failures.clear()


# --------------------------------------------------------------------------- #
# Base de données isolée
# --------------------------------------------------------------------------- #
@pytest.fixture
async def db_engine():
    """Moteur neuf + schéma vierge pour chaque test (SQLite temporaire)."""
    # Les verrous asyncio sont recréés dans la boucle du test courant.
    db_manager._init_lock = asyncio.Lock()
    db_manager._table_creation_lock = asyncio.Lock()
    await db_manager.close_db()
    await db_manager.init_db()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    db_manager._initialized = True
    yield db_manager.engine
    await db_manager.close_db()


@pytest.fixture
async def db_session(db_engine):
    async with db_manager.async_session_maker() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# --------------------------------------------------------------------------- #
# Utilisateurs / jetons
# --------------------------------------------------------------------------- #
def make_token(user_id: str, email: str = "", role: str = "user", name: Optional[str] = None) -> str:
    claims: Dict[str, Any] = {"sub": user_id, "email": email, "role": role}
    if name:
        claims["name"] = name
    return create_access_token(claims)


def auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def candidate(db_session):
    """Candidat enregistré en base + en-têtes d'auth."""
    from models.auth import User

    user = User(id="cand-1", email="candidat@emploi-tests.ci", name="Awa Candidate", role="user")
    db_session.add(user)
    await db_session.commit()
    token = make_token("cand-1", "candidat@emploi-tests.ci", "user", "Awa Candidate")
    return {"id": "cand-1", "email": "candidat@emploi-tests.ci", "headers": auth_headers(token)}


@pytest.fixture
async def admin(db_session):
    """Admin enregistré en base (destinataire des notifications) + en-têtes d'auth."""
    from models.auth import User

    user = User(id="admin-1", email="admin@emploi-tests.ci", name="Admin", role="admin")
    db_session.add(user)
    await db_session.commit()
    token = make_token("admin-1", "admin@emploi-tests.ci", "admin", "Admin")
    return {"id": "admin-1", "email": "admin@emploi-tests.ci", "headers": auth_headers(token)}
