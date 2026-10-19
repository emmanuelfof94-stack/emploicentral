"""Paiement Wave Checkout (routers/payments.py, services/wave.py) — API Wave simulée."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from sqlalchemy import select

from models.course_purchases import Course_purchases
from models.wave_checkouts import Wave_checkouts
from routers import course_access
from services import training_quota, wave

BASE = "/api/v1/payments/wave"
SECRET = "wave_sn_WHS_test"


def _sign(body: bytes, secret: str = SECRET, ts: int = None) -> str:
    ts = int(time.time()) if ts is None else ts
    sig = hmac.new(secret.encode(), str(ts).encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _session(checkout_id: int, payment_status="processing", checkout_status="open", amount="20000",
             currency="XOF", session_id="cos-test1"):
    return {
        "id": session_id, "amount": amount, "currency": currency, "client_reference": f"ec-{checkout_id}",
        "checkout_status": checkout_status, "payment_status": payment_status,
        "transaction_id": "T_ABC123" if payment_status == "succeeded" else None,
        "wave_launch_url": f"https://pay.wave.com/c/{session_id}",
    }


@pytest.fixture
def wave_on(monkeypatch):
    monkeypatch.setenv("WAVE_API_KEY", "wave_ci_prod_test")
    monkeypatch.setenv("WAVE_WEBHOOK_SECRET", SECRET)
    created = []

    async def fake_create(amount, client_reference, success_url, error_url):
        created.append({"amount": amount, "client_reference": client_reference,
                        "success_url": success_url, "error_url": error_url})
        return _session(int(client_reference.split("-")[1]), amount=amount)

    monkeypatch.setattr(wave, "create_checkout_session", fake_create)
    return created


@pytest.fixture
def sales_open(monkeypatch):
    monkeypatch.setitem(course_access.PAID_COURSES["pmp"], "sales_paused", False)


async def _start(client, candidate, slug="pmp"):
    r = await client.post(f"{BASE}/checkout", json={"slug": slug}, headers=candidate["headers"])
    assert r.status_code == 200, r.text
    return r.json()


# ---------- services/wave ----------
def test_amount_xof():
    assert wave.amount_xof("20 000 FCFA") == "20000"
    assert wave.amount_xof("2 000 FCFA") == "2000"
    with pytest.raises(ValueError):
        wave.amount_xof("gratuit")


def test_signature_valid_and_invalid():
    body = b'{"id":"EV_1","type":"checkout.session.completed"}'
    assert wave.verify_webhook_signature(body, _sign(body), SECRET)
    assert not wave.verify_webhook_signature(body, _sign(body, secret="autre"), SECRET)
    assert not wave.verify_webhook_signature(body + b" ", _sign(body), SECRET)  # corps modifié
    assert not wave.verify_webhook_signature(body, _sign(body), "")  # pas de secret configuré
    assert not wave.verify_webhook_signature(body, "n'importe quoi", SECRET)


def test_signature_rejects_replay_and_accepts_rotated_key():
    body = b"{}"
    old = int(time.time()) - 3600
    assert not wave.verify_webhook_signature(body, _sign(body, ts=old), SECRET)
    ts = int(time.time())
    good = _sign(body, ts=ts).split("v1=")[1]
    assert wave.verify_webhook_signature(body, f"t={ts},v1=deadbeef,v1={good}", SECRET)


# ---------- Création de session ----------
async def test_checkout_disabled_without_api_key(client, candidate, sales_open, monkeypatch):
    monkeypatch.delenv("WAVE_API_KEY", raising=False)
    r = await client.post(f"{BASE}/checkout", json={"slug": "pmp"}, headers=candidate["headers"])
    assert r.status_code == 503
    assert (await client.get(f"{BASE}/config")).json() == {"enabled": False}


async def test_checkout_requires_auth(client, wave_on, sales_open):
    assert (await client.post(f"{BASE}/checkout", json={"slug": "pmp"})).status_code == 401


async def test_checkout_creates_session(client, db_session, candidate, wave_on, sales_open):
    body = await _start(client, candidate)
    assert body["launch_url"].startswith("https://pay.wave.com/")
    sent = wave_on[0]
    assert sent["amount"] == "20000" and sent["client_reference"] == f"ec-{body['checkout_id']}"
    assert sent["success_url"].startswith("https://") and "checkout=" in sent["success_url"]
    row = (await db_session.execute(select(Wave_checkouts))).scalars().one()
    assert row.session_id == "cos-test1" and row.user_id == candidate["id"]
    # Aucun achat tant que Wave n'a pas confirmé le paiement.
    assert (await db_session.execute(select(Course_purchases))).scalars().all() == []


async def test_checkout_refused_when_sales_paused(client, candidate, wave_on, monkeypatch):
    monkeypatch.setitem(course_access.PAID_COURSES["pmp"], "sales_paused", True)
    r = await client.post(f"{BASE}/checkout", json={"slug": "pmp"}, headers=candidate["headers"])
    assert r.status_code == 403


async def test_checkout_unlimited_refused_while_quota_disabled(client, candidate, wave_on, monkeypatch):
    monkeypatch.setenv("TRAINING_QUOTA_ENABLED", "false")
    r = await client.post(f"{BASE}/checkout", json={"slug": training_quota.UNLIMITED_SLUG},
                          headers=candidate["headers"])
    assert r.status_code == 403


async def test_checkout_unknown_product(client, candidate, wave_on):
    r = await client.post(f"{BASE}/checkout", json={"slug": "inconnu"}, headers=candidate["headers"])
    assert r.status_code == 404


async def test_checkout_refused_when_already_paid(client, db_session, candidate, wave_on, sales_open):
    db_session.add(Course_purchases(user_id=candidate["id"], course_slug="pmp", status="paid"))
    await db_session.commit()
    r = await client.post(f"{BASE}/checkout", json={"slug": "pmp"}, headers=candidate["headers"])
    assert r.status_code == 409


# ---------- Retour du candidat (relecture chez Wave) ----------
async def test_return_unlocks_access_after_wave_confirms(client, db_session, candidate, wave_on, sales_open, monkeypatch):
    started = await _start(client, candidate)
    cid = started["checkout_id"]

    async def fake_get(session_id):
        return _session(cid, payment_status="succeeded", checkout_status="complete")

    monkeypatch.setattr(wave, "get_checkout_session", fake_get)
    r = await client.get(f"{BASE}/checkout/{cid}", headers=candidate["headers"])
    assert r.json()["status"] == "paid"
    purchase = (await db_session.execute(select(Course_purchases))).scalars().one()
    assert purchase.status == "paid" and "T_ABC123" in purchase.payment_ref
    access = (await client.get("/api/v1/course-access/pmp/status", headers=candidate["headers"])).json()
    assert access["has_access"] is True and access["wave_enabled"] is True
    # Idempotent : un second retour ne crée pas de doublon.
    await client.get(f"{BASE}/checkout/{cid}", headers=candidate["headers"])
    assert len((await db_session.execute(select(Course_purchases))).scalars().all()) == 1


async def test_return_pending_while_processing(client, candidate, wave_on, sales_open, monkeypatch):
    cid = (await _start(client, candidate))["checkout_id"]

    async def fake_get(session_id):
        return _session(cid)

    monkeypatch.setattr(wave, "get_checkout_session", fake_get)
    assert (await client.get(f"{BASE}/checkout/{cid}", headers=candidate["headers"])).json()["status"] == "pending"


async def test_amount_mismatch_never_unlocks(client, db_session, candidate, wave_on, sales_open, monkeypatch):
    cid = (await _start(client, candidate))["checkout_id"]

    async def fake_get(session_id):
        return _session(cid, payment_status="succeeded", checkout_status="complete", amount="100")

    monkeypatch.setattr(wave, "get_checkout_session", fake_get)
    assert (await client.get(f"{BASE}/checkout/{cid}", headers=candidate["headers"])).json()["status"] != "paid"
    assert (await db_session.execute(select(Course_purchases))).scalars().all() == []


async def test_other_user_cannot_read_checkout(client, candidate, admin, wave_on, sales_open):
    cid = (await _start(client, candidate))["checkout_id"]
    assert (await client.get(f"{BASE}/checkout/{cid}", headers=admin["headers"])).status_code == 404


# ---------- Webhook ----------
async def test_webhook_unlocks_access(client, db_session, candidate, wave_on, sales_open):
    cid = (await _start(client, candidate))["checkout_id"]
    body = json.dumps({"id": "EV_1", "type": "checkout.session.completed",
                       "data": _session(cid, payment_status="succeeded", checkout_status="complete")}).encode()
    r = await client.post(f"{BASE}/webhook", content=body, headers={"Wave-Signature": _sign(body)})
    assert r.status_code == 200
    purchase = (await db_session.execute(select(Course_purchases))).scalars().one()
    assert purchase.status == "paid" and purchase.user_id == candidate["id"]
    # Webhook rejoué : toujours une seule ligne.
    r = await client.post(f"{BASE}/webhook", content=body, headers={"Wave-Signature": _sign(body)})
    assert r.status_code == 200
    assert len((await db_session.execute(select(Course_purchases))).scalars().all()) == 1


async def test_webhook_rejects_bad_signature(client, db_session, candidate, wave_on, sales_open):
    cid = (await _start(client, candidate))["checkout_id"]
    body = json.dumps({"id": "EV_2", "type": "checkout.session.completed",
                       "data": _session(cid, payment_status="succeeded", checkout_status="complete")}).encode()
    r = await client.post(f"{BASE}/webhook", content=body, headers={"Wave-Signature": _sign(body, secret="faux")})
    assert r.status_code == 401
    assert (await db_session.execute(select(Course_purchases))).scalars().all() == []


async def test_webhook_forged_reference_is_ignored(client, db_session, candidate, wave_on, sales_open):
    cid = (await _start(client, candidate))["checkout_id"]
    forged = _session(cid + 99, payment_status="succeeded", checkout_status="complete")  # mauvaise référence
    body = json.dumps({"id": "EV_3", "type": "checkout.session.completed", "data": forged}).encode()
    assert (await client.post(f"{BASE}/webhook", content=body, headers={"Wave-Signature": _sign(body)})).status_code == 200
    assert (await db_session.execute(select(Course_purchases))).scalars().all() == []


async def test_webhook_unknown_session_acknowledged(client, wave_on):
    body = json.dumps({"id": "EV_4", "type": "checkout.session.completed",
                       "data": {"id": "cos-inconnue"}}).encode()
    assert (await client.post(f"{BASE}/webhook", content=body, headers={"Wave-Signature": _sign(body)})).status_code == 200
