"""Auth locale : inscription, connexion, refus, endpoints protégés."""
from __future__ import annotations

import pytest

from core.auth import decode_access_token
from services.auth import hash_password, validate_password_strength, verify_password
from tests.conftest import auth_headers

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
GOOD_PWD = "Kp7!vertMangue"


async def _register(client, email="awa@emploi-tests.ci", password=GOOD_PWD, name="Awa"):
    return await client.post(REGISTER, json={"email": email, "password": password, "name": name})


# ---------- Hachage / politique de mot de passe (pur) ----------
def test_hash_password_roundtrip():
    stored = hash_password(GOOD_PWD)
    assert stored.startswith("pbkdf2_sha256$")
    assert GOOD_PWD not in stored
    assert verify_password(GOOD_PWD, stored)
    assert not verify_password("mauvais-mot", stored)


@pytest.mark.parametrize("stored", [None, "", "garbage", "md5$1$aa$bb"])
def test_verify_password_rejects_invalid_hashes(stored):
    assert verify_password(GOOD_PWD, stored) is False


@pytest.mark.parametrize(
    "pwd,email",
    [("court", None), ("azerty123", None), ("PASSWORD", None), ("awakone", "awakone@emploi-tests.ci")],
)
def test_validate_password_strength_rejects_weak(pwd, email):
    with pytest.raises(ValueError):
        validate_password_strength(pwd, email)


# ---------- Register ----------
async def test_register_returns_valid_token(client):
    r = await _register(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer"
    claims = decode_access_token(body["token"])
    assert claims["email"] == "awa@emploi-tests.ci"
    assert claims["role"] == "user"
    assert claims["sub"].startswith("local:")


async def test_register_normalizes_email_and_rejects_duplicate(client):
    assert (await _register(client, email="Awa@Emploi-Tests.ci")).status_code == 200
    dup = await _register(client, email="awa@emploi-tests.ci")
    assert dup.status_code == 409


async def test_register_rejects_weak_password(client):
    # Trop courant : passe la validation Pydantic (>= 8) mais refusé par la politique
    # → 400 (409 est réservé à « email déjà utilisé »).
    r = await _register(client, password="azerty123")
    assert r.status_code == 400
    assert "courant" in r.json()["detail"]
    # Trop court : refusé dès la validation du schéma.
    assert (await _register(client, email="b@emploi-tests.ci", password="abc")).status_code == 422


async def test_register_admin_email_gets_admin_role(client):
    r = await _register(client, email="admin@emploi-tests.ci")
    assert decode_access_token(r.json()["token"])["role"] == "admin"


# ---------- Login ----------
async def test_login_success_and_me(client):
    await _register(client)
    r = await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": GOOD_PWD})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    me = await client.get(ME, headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "awa@emploi-tests.ci"


async def test_login_is_case_insensitive_on_email(client):
    await _register(client)
    r = await client.post(LOGIN, json={"email": "AWA@emploi-tests.CI", "password": GOOD_PWD})
    assert r.status_code == 200


async def test_login_wrong_password_is_401(client):
    await _register(client)
    r = await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": "pas-le-bon-mdp"})
    assert r.status_code == 401
    assert "token" not in r.json()


async def test_login_unknown_email_is_401(client):
    r = await client.post(LOGIN, json={"email": "inconnu@emploi-tests.ci", "password": GOOD_PWD})
    assert r.status_code == 401


async def test_login_rate_limited_after_repeated_failures(client):
    await _register(client)
    from services import rate_limit

    for _ in range(rate_limit.MAX_ATTEMPTS):
        r = await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": "mauvais-mdp"})
        assert r.status_code == 401
    blocked = await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": GOOD_PWD})
    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers.keys()}


async def test_login_remember_me_gives_longer_token(client):
    await _register(client)
    short = (await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": GOOD_PWD})).json()
    long_ = (
        await client.post(LOGIN, json={"email": "awa@emploi-tests.ci", "password": GOOD_PWD, "remember": True})
    ).json()
    assert long_["expires_at"] > short["expires_at"]


# ---------- Endpoints protégés ----------
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/change-password"),
        ("GET", "/api/v1/training-access/quota"),
        ("POST", "/api/v1/training-access/purchase-request"),
        ("GET", "/api/v1/course-access/pmp/status"),
        ("GET", "/api/v1/course-access/pmp/content"),
        ("GET", "/api/v1/course-access/admin/purchases"),
        ("GET", "/api/v1/training-courses"),
    ],
)
async def test_protected_endpoints_require_token(client, method, path):
    r = await client.request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


async def test_invalid_token_is_401(client):
    r = await client.get(ME, headers=auth_headers("pas.un.jwt"))
    assert r.status_code == 401


async def test_token_signed_with_other_secret_is_401(client):
    from jose import jwt

    forged = jwt.encode({"sub": "x", "email": "x@emploi-tests.ci", "role": "admin"}, "autre-secret", algorithm="HS256")
    r = await client.get(ME, headers=auth_headers(forged))
    assert r.status_code == 401


async def test_admin_endpoint_forbidden_for_regular_user(client, candidate):
    r = await client.get("/api/v1/course-access/admin/purchases", headers=candidate["headers"])
    assert r.status_code == 403
