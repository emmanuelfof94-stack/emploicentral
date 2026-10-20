"""Failles faibles du test d'intrusion du 2026-10-19."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from models.analytics import PageView
from routers import analytics
from tests.conftest import make_token


@pytest.fixture(autouse=True)
def _reset_track_limit():
    analytics._track_hits.clear()
    yield
    analytics._track_hits.clear()


async def test_jwt_in_query_string_is_rejected(client, candidate):
    token = make_token(candidate["id"], candidate["email"], "user")
    r = await client.get("/api/v1/notifications", params={"token": token})
    assert r.status_code == 401
    # Le même jeton reste valable dans l'en-tête Authorization.
    r = await client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_admin_settings_routes_are_gone(client, admin):
    r = await client.get("/api/v1/admin/settings", headers=admin["headers"])
    assert r.status_code in (404, 405) or "application/json" not in r.headers.get("content-type", "")
    r = await client.put("/api/v1/admin/settings/backend/JWT_SECRET_KEY",
                         headers=admin["headers"], json={"value": "pwned"})
    assert r.status_code in (404, 405)


async def test_track_is_rate_limited_per_visitor(client, db_session, monkeypatch):
    monkeypatch.setattr(analytics, "TRACK_MAX_PER_WINDOW", 5)
    for i in range(12):
        r = await client.post("/api/v1/analytics/track", json={"path": f"/p{i}"},
                              headers={"user-agent": "Mozilla/5.0 " + "x" * 500})
        assert r.status_code == 204
    n = (await db_session.execute(select(func.count(PageView.id)))).scalar()
    assert n == 5
    ua = (await db_session.execute(select(PageView.user_agent).limit(1))).scalar()
    assert len(ua) <= 200
