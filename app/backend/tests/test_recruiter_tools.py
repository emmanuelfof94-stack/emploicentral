"""Espace recruteur : « Mon entreprise », statistiques (vues), candidats triés par score,
et notifications push (abonnement + envoi lors des alertes)."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select

from models.analytics import PageView
from models.auth import User
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from models.job_views import Job_views
from models.push_subscriptions import Push_subscriptions
from models.recruiter_profiles import Recruiter_profiles
from models.user_jobs import User_jobs
from models.user_profiles import User_profiles
from services import web_push
from tests.conftest import auth_headers, make_token


@pytest.fixture
async def recruiter(db_session):
    db_session.add(User(id="rec-1", email="rh@entreprise.ci", name="RH", role="recruiter"))
    db_session.add(Recruiter_profiles(user_id="rec-1", company_name="Groupe Atlantique",
                                      contact_phone="0700000000"))
    db_session.add(Job_offers(id=10, title="Comptable", company="Groupe Atlantique", location="Abidjan",
                              sector="Finance", requirements="SYSCOHADA, SAGE, Excel", is_active=True,
                              source="Recruteur"))
    db_session.add(Job_postings(job_id=10, posted_by="rec-1", company_name="Groupe Atlantique",
                                status="approved"))
    await db_session.commit()
    return {"id": "rec-1", "headers": auth_headers(make_token("rec-1", "rh@entreprise.ci", "recruiter"))}


async def _count(db, model, *where):
    return int((await db.execute(select(func.count(model.id)).where(*where))).scalar() or 0)


# ---------- Mon entreprise ----------
async def test_company_get_and_update_whatsapp(client, recruiter):
    r = await client.get("/api/v1/recruiter/company", headers=recruiter["headers"])
    assert r.status_code == 200
    assert r.json()["company_name"] == "Groupe Atlantique"
    assert r.json()["whatsapp"] == "2250700000000"

    r = await client.put("/api/v1/recruiter/company", headers=recruiter["headers"],
                         json={"contact_phone": "+225 05 11 22 33 44", "website": "atlantique.ci"})
    assert r.status_code == 200
    body = r.json()
    assert body["contact_phone"] == "+225 05 11 22 33 44"
    assert body["whatsapp"] == "2250511223344"
    assert body["website"] == "https://atlantique.ci"


async def test_company_update_rejects_bad_phone_and_empty_name(client, recruiter):
    r = await client.put("/api/v1/recruiter/company", headers=recruiter["headers"],
                         json={"contact_phone": "12"})
    assert r.status_code == 400
    r = await client.put("/api/v1/recruiter/company", headers=recruiter["headers"],
                         json={"company_name": "  "})
    assert r.status_code == 400


async def test_new_whatsapp_number_used_by_apply_button(client, recruiter, candidate):
    await client.put("/api/v1/recruiter/company", headers=recruiter["headers"],
                     json={"contact_phone": "+225 05 11 22 33 44"})
    r = await client.get("/api/v1/recruiter/contact/10", headers=candidate["headers"])
    assert r.json()["whatsapp"] == "2250511223344"


async def test_company_requires_recruiter_role(client, candidate):
    r = await client.get("/api/v1/recruiter/company", headers=candidate["headers"])
    assert r.status_code == 403


# ---------- Vues + statistiques ----------
async def test_views_counted_once_per_candidate_per_day(client, db_session, recruiter, candidate):
    for _ in range(3):
        await client.get("/api/v1/recruiter/contact/10", headers=candidate["headers"])
    # Le recruteur qui consulte sa propre offre ne compte pas.
    await client.get("/api/v1/recruiter/contact/10", headers=recruiter["headers"])
    assert await _count(db_session, Job_views, Job_views.job_id == 10) == 1


async def test_stats_combine_app_and_public_views(client, db_session, recruiter, candidate):
    await client.get("/api/v1/recruiter/contact/10", headers=candidate["headers"])
    now = datetime.now()
    db_session.add_all([
        PageView(path="/offres/10", visitor_hash="v1", is_bot=False, created_at=now),
        PageView(path="/offres/10", visitor_hash="v1", is_bot=False, created_at=now),  # même visiteur
        PageView(path="/offres/10", visitor_hash="v2", is_bot=False, created_at=now),
        PageView(path="/offres/10", visitor_hash="bot", is_bot=True, created_at=now),   # robot exclu
        PageView(path="/offres/99", visitor_hash="v3", is_bot=False, created_at=now),   # autre offre
    ])
    db_session.add(User_jobs(user_id=candidate["id"], job_id=10, status="applied", saved=True))
    await db_session.commit()

    r = await client.get("/api/v1/recruiter/stats", headers=recruiter["headers"])
    assert r.status_code == 200
    s = r.json()
    assert s["views"] == 3 and s["views_7d"] == 3
    assert s["applicants"] == 1 and s["saves"] == 1 and s["offers_online"] == 1
    assert s["jobs"][0]["job_id"] == 10 and s["jobs"][0]["views"] == 3


# ---------- Candidats triés par score ----------
async def test_candidates_sorted_by_score(client, db_session, recruiter):
    for uid, skills, sector in [
        ("c-weak", "Cuisine, Pâtisserie", "Restauration"),
        ("c-strong", "SYSCOHADA, SAGE, Excel, Comptabilité", "Finance"),
        ("c-empty", None, None),
    ]:
        db_session.add(User(id=uid, email=f"{uid}@x.ci", role="user"))
        db_session.add(User_profiles(user_id=uid, full_name=uid, skills=skills, sector=sector,
                                     location="Abidjan", cv_analyzed=bool(skills)))
        db_session.add(User_jobs(user_id=uid, job_id=10, status="applied"))
    await db_session.commit()

    r = await client.get("/api/v1/recruiter/jobs/10/candidates", headers=recruiter["headers"])
    rows = r.json()
    assert [c["user_id"] for c in rows] == ["c-strong", "c-weak", "c-empty"]
    assert rows[0]["score"] > rows[1]["score"]
    assert rows[2]["score"] is None


# ---------- Push ----------
async def test_push_config_disabled_without_keys(client):
    r = await client.get("/api/v1/push/config")
    assert r.json() == {"available": False, "public_key": None}


async def test_push_subscribe_is_idempotent_per_endpoint(client, db_session, candidate):
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    for _ in range(2):
        r = await client.post("/api/v1/push/subscribe", headers=candidate["headers"], json=sub)
        assert r.status_code == 200
    assert await _count(db_session, Push_subscriptions) == 1
    r = await client.post("/api/v1/push/subscribe", headers=candidate["headers"],
                          json={**sub, "endpoint": "http://insecure"})
    assert r.status_code == 400
    await client.post("/api/v1/push/unsubscribe", headers=candidate["headers"], json={"endpoint": sub["endpoint"]})
    assert await _count(db_session, Push_subscriptions) == 0


async def test_send_to_user_drops_expired_subscriptions(db_session, monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    db_session.add_all([
        Push_subscriptions(user_id="u1", endpoint="https://push.example/ok", p256dh="k", auth="a"),
        Push_subscriptions(user_id="u1", endpoint="https://push.example/gone", p256dh="k", auth="a"),
    ])
    await db_session.commit()
    sent_payloads = []

    def fake_send(sub, payload):
        sent_payloads.append(payload)
        return 410 if sub["endpoint"].endswith("gone") else 201

    monkeypatch.setattr(web_push, "_send_sync", fake_send)
    sent = await web_push.send_to_user(db_session, "u1", {"title": "t", "body": "b", "url": "/jobs"})
    assert sent == 1 and len(sent_payloads) == 2
    assert await _count(db_session, Push_subscriptions) == 1


async def test_new_offer_alert_sends_push(db_session, monkeypatch):
    from services import notifications

    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    db_session.add(User_profiles(user_id="u1", full_name="Awa", skills="SYSCOHADA, SAGE, Excel",
                                 sector="Finance", location="Abidjan", cv_analyzed=True))
    db_session.add(Job_offers(id=20, title="Comptable", company="ABC", sector="Finance", location="Abidjan",
                              requirements="SYSCOHADA, SAGE", is_active=True, source="Emploi.ci"))
    db_session.add(Push_subscriptions(user_id="u1", endpoint="https://push.example/u1", p256dh="k", auth="a"))
    await db_session.commit()
    calls = []

    async def fake_send_to_user(session, user_id, payload):
        calls.append((user_id, payload))
        return 1

    monkeypatch.setattr(web_push, "send_to_user", fake_send_to_user)
    created = await notifications.dispatch_new_offer_alerts()
    assert created == 1
    assert calls and calls[0][0] == "u1"
    assert calls[0][1]["title"] == "Nouvelle offre pour vous" and "Comptable" in calls[0][1]["body"]
