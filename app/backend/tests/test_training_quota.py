"""Quota d'accès aux formations (services/training_quota.py + routers associés)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from models.course_purchases import Course_purchases
from models.notifications import Notification
from models.training_access import Training_access_events
from models.training_courses import Training_courses
from services import training_quota as tq

QUOTA_URL = "/api/v1/training-access/quota"
PURCHASE_URL = "/api/v1/training-access/purchase-request"


@pytest.fixture
def quota_on(monkeypatch):
    monkeypatch.setenv("TRAINING_QUOTA_ENABLED", "true")


@pytest.fixture
def quota_off(monkeypatch):
    monkeypatch.delenv("TRAINING_QUOTA_ENABLED", raising=False)


async def _count(db, model, *where):
    return int((await db.execute(select(func.count(model.id)).where(*where))).scalar() or 0)


async def _grant_unlimited(db, user_id, status="paid"):
    db.add(Course_purchases(user_id=user_id, course_slug=tq.UNLIMITED_SLUG, status=status, amount=tq.UNLIMITED_PRICE))
    await db.commit()


# ---------- Interrupteur ----------
@pytest.mark.parametrize("value,expected", [
    (None, False), ("", False), ("false", False), ("0", False),
    ("true", True), ("1", True), ("YES", True), (" on ", True),
])
def test_quota_enabled_switch(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("TRAINING_QUOTA_ENABLED", raising=False)
    else:
        monkeypatch.setenv("TRAINING_QUOTA_ENABLED", value)
    assert tq.quota_enabled() is expected


# ---------- Verrou levé (défaut) ----------
async def test_quota_off_consumes_nothing(db_session, quota_off):
    for i in range(tq.FREE_ACCESS_LIMIT + 3):
        await tq.consume(db_session, "u1", "catalog", str(i))
    assert await tq.used_count(db_session, "u1") == 0
    assert await tq.has_remaining(db_session, "u1") is True
    q = await tq.get_quota(db_session, "u1")
    assert q["enabled"] is False


async def test_quota_off_ignores_existing_events(db_session, quota_off):
    for i in range(tq.FREE_ACCESS_LIMIT):
        db_session.add(Training_access_events(user_id="u1", kind="catalog", ref=str(i)))
    await db_session.commit()
    assert await tq.has_remaining(db_session, "u1") is True


# ---------- Verrou actif ----------
async def test_free_limit_then_402(db_session, quota_on):
    for i in range(tq.FREE_ACCESS_LIMIT):
        assert await tq.has_remaining(db_session, "u1")
        await tq.consume(db_session, "u1", "catalog", f"c{i}")
    assert await tq.used_count(db_session, "u1") == tq.FREE_ACCESS_LIMIT
    assert await tq.has_remaining(db_session, "u1") is False
    with pytest.raises(HTTPException) as exc:
        await tq.consume(db_session, "u1", "generate", "new")
    assert exc.value.status_code == 402
    assert exc.value.detail["code"] == tq.QUOTA_CODE
    # Aucun événement supplémentaire journalisé après le refus.
    assert await tq.used_count(db_session, "u1") == tq.FREE_ACCESS_LIMIT


async def test_consume_is_idempotent_per_kind_and_ref(db_session, quota_on):
    await tq.consume(db_session, "u1", "catalog", "42")
    await tq.consume(db_session, "u1", "catalog", "42")
    assert await tq.used_count(db_session, "u1") == 1
    # Même ref mais autre type d'accès → compte à part.
    await tq.consume(db_session, "u1", "generate", "42")
    assert await tq.used_count(db_session, "u1") == 2


async def test_already_consumed_ref_allowed_even_when_exhausted(db_session, quota_on):
    for i in range(tq.FREE_ACCESS_LIMIT):
        await tq.consume(db_session, "u1", "catalog", f"c{i}")
    await tq.consume(db_session, "u1", "catalog", "c0")  # ne lève pas
    assert await tq.used_count(db_session, "u1") == tq.FREE_ACCESS_LIMIT


async def test_consume_without_ref_always_counts(db_session, quota_on):
    await tq.consume(db_session, "u1", "generate", None)
    await tq.consume(db_session, "u1", "generate", None)
    assert await tq.used_count(db_session, "u1") == 2


async def test_quota_is_per_user(db_session, quota_on):
    for i in range(tq.FREE_ACCESS_LIMIT):
        await tq.consume(db_session, "u1", "catalog", f"c{i}")
    assert await tq.has_remaining(db_session, "u2") is True


async def test_unlimited_requires_paid_purchase(db_session, quota_on):
    for i in range(tq.FREE_ACCESS_LIMIT):
        await tq.consume(db_session, "u1", "catalog", f"c{i}")
    await _grant_unlimited(db_session, "u1", status="pending")
    assert await tq.has_unlimited(db_session, "u1") is False
    assert await tq.has_remaining(db_session, "u1") is False

    await _grant_unlimited(db_session, "u1", status="paid")
    assert await tq.has_unlimited(db_session, "u1") is True
    assert await tq.has_remaining(db_session, "u1") is True
    await tq.consume(db_session, "u1", "catalog", "extra")  # ne lève plus
    q = await tq.get_quota(db_session, "u1")
    assert q["unlimited"] is True and q["remaining"] is None


async def test_paid_purchase_of_other_product_does_not_grant_unlimited(db_session, quota_on):
    db_session.add(Course_purchases(user_id="u1", course_slug="pmp", status="paid"))
    await db_session.commit()
    assert await tq.has_unlimited(db_session, "u1") is False


async def test_get_quota_counts_and_purchase_status(db_session, quota_on):
    await tq.consume(db_session, "u1", "catalog", "a")
    await tq.consume(db_session, "u1", "catalog", "b")
    q = await tq.get_quota(db_session, "u1")
    assert q == {
        "enabled": True, "limit": tq.FREE_ACCESS_LIMIT, "used": 2,
        "remaining": tq.FREE_ACCESS_LIMIT - 2, "unlimited": False,
        "purchase_status": "none", "slug": tq.UNLIMITED_SLUG, "price": tq.UNLIMITED_PRICE,
    }
    await _grant_unlimited(db_session, "u1", status="rejected")
    assert (await tq.get_quota(db_session, "u1"))["purchase_status"] == "rejected"


async def test_notify_quota_blocked_is_deduplicated(db_session):
    await tq.notify_quota_blocked(db_session, "u1")
    await tq.notify_quota_blocked(db_session, "u1")
    assert await _count(db_session, Notification, Notification.user_id == "u1") == 1


# ---------- Routes HTTP /training-access ----------
async def test_quota_endpoint(client, candidate, quota_on):
    r = await client.get(QUOTA_URL, headers=candidate["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["remaining"] == tq.FREE_ACCESS_LIMIT
    assert body["purchase_status"] == "none"
    assert body["payment_number"]
    assert body["wave_enabled"] is False  # pas de WAVE_API_KEY en test


async def test_quota_endpoint_exposes_wave(client, candidate, quota_on, monkeypatch):
    monkeypatch.setenv("WAVE_API_KEY", "wave_ci_prod_test")
    r = await client.get(QUOTA_URL, headers=candidate["headers"])
    assert r.json()["wave_enabled"] is True


async def test_purchase_request_flow_until_admin_validation(client, db_session, candidate, admin, quota_on):
    r = await client.post(PURCHASE_URL, json={"payment_ref": "WAVE-123"}, headers=candidate["headers"])
    assert r.status_code == 200
    assert r.json()["purchase_status"] == "pending"
    assert r.json()["unlimited"] is False

    # Deuxième déclaration : la ligne pending est réutilisée (pas de doublon).
    r = await client.post(PURCHASE_URL, json={"payment_ref": "WAVE-456"}, headers=candidate["headers"])
    assert r.status_code == 200
    rows = (await db_session.execute(
        select(Course_purchases).where(Course_purchases.user_id == candidate["id"])
    )).scalars().all()
    assert len(rows) == 1 and rows[0].status == "pending" and rows[0].payment_ref == "WAVE-456"

    # L'admin a été notifié in-app.
    assert await _count(db_session, Notification, Notification.user_id == admin["id"]) >= 1

    # Un candidat ne peut pas valider lui-même.
    forbidden = await client.post(
        f"/api/v1/course-access/admin/purchases/{rows[0].id}/validate", headers=candidate["headers"]
    )
    assert forbidden.status_code == 403

    ok = await client.post(f"/api/v1/course-access/admin/purchases/{rows[0].id}/validate", headers=admin["headers"])
    assert ok.status_code == 200

    q = (await client.get(QUOTA_URL, headers=candidate["headers"])).json()
    assert q["unlimited"] is True and q["remaining"] is None and q["purchase_status"] == "paid"
    # Le candidat est notifié du déblocage.
    assert await _count(db_session, Notification, Notification.user_id == candidate["id"]) == 1


async def test_purchase_request_when_already_unlimited_is_noop(client, db_session, candidate, quota_on):
    await _grant_unlimited(db_session, candidate["id"])
    r = await client.post(PURCHASE_URL, json={}, headers=candidate["headers"])
    assert r.status_code == 200 and r.json()["unlimited"] is True
    assert await _count(db_session, Course_purchases, Course_purchases.user_id == candidate["id"]) == 1


async def test_new_request_after_rejection_creates_new_pending(client, db_session, candidate, quota_on):
    await _grant_unlimited(db_session, candidate["id"], status="rejected")
    r = await client.post(PURCHASE_URL, json={"payment_ref": "OM-1"}, headers=candidate["headers"])
    assert r.json()["purchase_status"] == "pending"
    assert await _count(db_session, Course_purchases, Course_purchases.user_id == candidate["id"]) == 2


# ---------- Déblocage d'une formation gratuite du catalogue ----------
async def _make_courses(db, n_free, n_paid=0):
    ids = []
    for i in range(n_free):
        c = Training_courses(title=f"Gratuite {i}", is_free=True, is_active=True, url=f"https://f/{i}")
        db.add(c)
        ids.append(c)
    paid = []
    for i in range(n_paid):
        c = Training_courses(title=f"Payante {i}", is_free=False, is_active=True, url=f"https://p/{i}")
        db.add(c)
        paid.append(c)
    await db.commit()
    return [c.id for c in ids], [c.id for c in paid]


async def test_unlock_consumes_quota_until_402(client, db_session, candidate, quota_on):
    free_ids, paid_ids = await _make_courses(db_session, tq.FREE_ACCESS_LIMIT + 1, 1)
    for cid in free_ids[:tq.FREE_ACCESS_LIMIT]:
        r = await client.post(f"/api/v1/training-courses/{cid}/unlock", headers=candidate["headers"])
        assert r.status_code == 200 and r.json()["url"]

    blocked = await client.post(f"/api/v1/training-courses/{free_ids[-1]}/unlock", headers=candidate["headers"])
    assert blocked.status_code == 402
    assert blocked.json()["detail"]["code"] == tq.QUOTA_CODE
    # Notif « quota atteint » créée une seule fois, même après plusieurs refus.
    await client.post(f"/api/v1/training-courses/{free_ids[-1]}/unlock", headers=candidate["headers"])
    assert await _count(
        db_session, Notification,
        Notification.user_id == candidate["id"], Notification.title == tq.BLOCK_NOTIF_TITLE,
    ) == 1

    # Une formation déjà débloquée reste accessible ; une payante n'est pas soumise au quota.
    again = await client.post(f"/api/v1/training-courses/{free_ids[0]}/unlock", headers=candidate["headers"])
    assert again.status_code == 200
    paid = await client.post(f"/api/v1/training-courses/{paid_ids[0]}/unlock", headers=candidate["headers"])
    assert paid.status_code == 200
    assert await tq.used_count(db_session, candidate["id"]) == tq.FREE_ACCESS_LIMIT


async def test_catalog_hides_free_urls_until_unlocked_when_quota_on(client, db_session, candidate, quota_on):
    free_ids, _ = await _make_courses(db_session, 2)
    await client.post(f"/api/v1/training-courses/{free_ids[0]}/unlock", headers=candidate["headers"])
    items = {c["id"]: c for c in (await client.get("/api/v1/training-courses", headers=candidate["headers"])).json()}
    assert items[free_ids[0]]["is_unlocked"] is True and items[free_ids[0]]["url"]
    assert items[free_ids[1]]["is_unlocked"] is False and items[free_ids[1]]["url"] is None


async def test_catalog_free_access_when_quota_off(client, db_session, candidate, quota_off):
    free_ids, _ = await _make_courses(db_session, 2)
    items = (await client.get("/api/v1/training-courses", headers=candidate["headers"])).json()
    assert all(c["is_unlocked"] is True and c["url"] for c in items)
    r = await client.post(f"/api/v1/training-courses/{free_ids[0]}/unlock", headers=candidate["headers"])
    assert r.status_code == 200
    assert await tq.used_count(db_session, candidate["id"]) == 0
