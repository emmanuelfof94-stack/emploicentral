"""Cours payants protégés (routers/course_access.py) : statut, vente suspendue, contenu."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from models.course_purchases import Course_purchases
from routers import course_access

BASE = "/api/v1/course-access"


async def _purchase(db, user_id, status, slug="pmp"):
    p = Course_purchases(user_id=user_id, course_slug=slug, status=status, amount="20 000 FCFA")
    db.add(p)
    await db.commit()
    return p.id


@pytest.fixture
def sales_open(monkeypatch):
    monkeypatch.setitem(course_access.PAID_COURSES["pmp"], "sales_paused", False)


@pytest.fixture
def sales_paused(monkeypatch):
    monkeypatch.setitem(course_access.PAID_COURSES["pmp"], "sales_paused", True)


async def test_unknown_course_is_404(client, candidate):
    r = await client.get(f"{BASE}/inconnu/status", headers=candidate["headers"])
    assert r.status_code == 404


async def test_status_without_purchase(client, candidate, sales_paused):
    body = (await client.get(f"{BASE}/pmp/status", headers=candidate["headers"])).json()
    assert body["has_access"] is False
    assert body["status"] == "none"
    assert body["sales_paused"] is True
    assert body["paused_reason"]


async def test_status_paused_reason_hidden_when_sales_open(client, candidate, sales_open):
    body = (await client.get(f"{BASE}/pmp/status", headers=candidate["headers"])).json()
    assert body["sales_paused"] is False and body["paused_reason"] is None


async def test_request_refused_when_sales_paused(client, db_session, candidate, sales_paused):
    r = await client.post(f"{BASE}/pmp/request", json={"payment_ref": "X"}, headers=candidate["headers"])
    assert r.status_code == 403
    rows = (await db_session.execute(select(Course_purchases))).scalars().all()
    assert rows == []


async def test_pending_request_not_updated_while_paused(client, db_session, candidate, sales_paused):
    pid = await _purchase(db_session, candidate["id"], "pending")
    r = await client.post(f"{BASE}/pmp/request", json={"payment_ref": "NEW"}, headers=candidate["headers"])
    assert r.status_code == 403
    row = (await db_session.execute(select(Course_purchases).where(Course_purchases.id == pid))).scalars().one()
    await db_session.refresh(row)
    assert row.status == "pending" and row.payment_ref is None


async def test_paid_user_keeps_access_while_paused(client, db_session, candidate, sales_paused):
    await _purchase(db_session, candidate["id"], "paid")
    r = await client.post(f"{BASE}/pmp/request", json={}, headers=candidate["headers"])
    assert r.status_code == 200 and r.json()["has_access"] is True
    content = await client.get(f"{BASE}/pmp/content", headers=candidate["headers"])
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("text/html")
    assert content.headers.get("cache-control") == "no-store"


async def test_request_creates_pending_when_sales_open(client, db_session, candidate, admin, sales_open):
    r = await client.post(f"{BASE}/pmp/request", json={"payment_ref": "WAVE-9"}, headers=candidate["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "pending" and r.json()["has_access"] is False
    r2 = await client.post(f"{BASE}/pmp/request", json={"payment_ref": "WAVE-10"}, headers=candidate["headers"])
    assert r2.status_code == 200
    rows = (await db_session.execute(select(Course_purchases))).scalars().all()
    assert len(rows) == 1 and rows[0].payment_ref == "WAVE-10"


@pytest.mark.parametrize("status", [None, "pending", "rejected"])
async def test_content_forbidden_without_paid_purchase(client, db_session, candidate, status):
    if status:
        await _purchase(db_session, candidate["id"], status)
    r = await client.get(f"{BASE}/pmp/content", headers=candidate["headers"])
    assert r.status_code == 403


async def test_paid_purchase_of_other_user_does_not_grant_access(client, db_session, candidate):
    await _purchase(db_session, "someone-else", "paid")
    r = await client.get(f"{BASE}/pmp/content", headers=candidate["headers"])
    assert r.status_code == 403


async def test_admin_validate_then_reject(client, db_session, candidate, admin):
    pid = await _purchase(db_session, candidate["id"], "pending")
    listing = await client.get(f"{BASE}/admin/purchases", headers=admin["headers"])
    assert listing.status_code == 200
    assert listing.json()[0]["user_email"] == candidate["email"]

    assert (await client.post(f"{BASE}/admin/purchases/{pid}/validate", headers=admin["headers"])).status_code == 200
    assert (await client.get(f"{BASE}/pmp/content", headers=candidate["headers"])).status_code == 200

    assert (await client.post(f"{BASE}/admin/purchases/{pid}/reject", headers=admin["headers"])).status_code == 200
    assert (await client.get(f"{BASE}/pmp/content", headers=candidate["headers"])).status_code == 403


async def test_admin_validate_unknown_purchase_is_404(client, admin):
    r = await client.post(f"{BASE}/admin/purchases/9999/validate", headers=admin["headers"])
    assert r.status_code == 404
