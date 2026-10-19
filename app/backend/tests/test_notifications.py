"""Matching des alertes emploi (services/notifications.py)."""
from __future__ import annotations

from typing import Any, List

import pytest
from sqlalchemy import select

from models.alert_preferences import Alert_preferences
from models.job_offers import Job_offers
from models.notifications import Notification
from models.user_profiles import User_profiles
from services import notifications as notif


def job(**kw: Any) -> Job_offers:
    base = dict(
        id=1, title="Développeur Python", company="Wave", location="Abidjan, Côte d'Ivoire",
        contract_type="CDI", sector="Informatique / Tech", description="API FastAPI et SQL",
        requirements="3 ans d'expérience", salary_range=None, is_active=True,
    )
    base.update(kw)
    return Job_offers(**base)


def pref(**kw: Any) -> Alert_preferences:
    base = dict(user_id="u1", sectors=None, locations=None, contract_types=None, keywords=None,
                min_salary=None, is_active=True)
    base.update(kw)
    return Alert_preferences(**base)


# ---------- _csv : piège du séparateur ----------
def test_csv_splits_on_pipe_used_by_frontend():
    # Le frontend joint secteurs/lieux/contrats avec « | » : sans ce découpage, la
    # préférence entière serait une seule sous-chaîne qui ne matche jamais.
    assert notif._csv("Informatique / Tech|Finance / Banque") == ["informatique / tech", "finance / banque"]


def test_csv_tolerates_comma_semicolon_newline_and_blanks():
    assert notif._csv(" Python, SQL ;Excel\n|  |") == ["python", "sql", "excel"]
    assert notif._csv(None) == []
    assert notif._csv("") == []


# ---------- match_offer ----------
def test_match_offer_multi_sector_pipe_preference():
    assert notif.match_offer(job(), pref(sectors="Santé|Informatique / Tech"))
    assert not notif.match_offer(job(), pref(sectors="Santé|Finance / Banque"))


def test_match_offer_location_with_comma_inside_value():
    # « Dakar, Sénégal » sur-découpé en ["dakar", "sénégal"] reste sans conséquence.
    assert notif.match_offer(job(location="Dakar, Sénégal"), pref(locations="Abidjan|Dakar, Sénégal"))
    assert not notif.match_offer(job(location="Lomé, Togo"), pref(locations="Abidjan|Dakar, Sénégal"))


def test_match_offer_is_case_insensitive():
    assert notif.match_offer(job(), pref(sectors="INFORMATIQUE", contract_types="cdi", keywords="FASTAPI"))


def test_match_offer_contract_filter():
    assert notif.match_offer(job(contract_type="CDD"), pref(contract_types="CDI|CDD"))
    assert not notif.match_offer(job(contract_type="Stage"), pref(contract_types="CDI|CDD"))


def test_match_offer_keywords_search_title_description_requirements():
    assert notif.match_offer(job(), pref(keywords="comptable, fastapi"))
    assert notif.match_offer(job(), pref(keywords="expérience"))
    assert not notif.match_offer(job(), pref(keywords="comptable, infirmier"))


def test_match_offer_all_criteria_must_hold():
    p = pref(sectors="Informatique / Tech", locations="Dakar")
    assert not notif.match_offer(job(), p)


def test_match_offer_inactive_job_never_matches():
    assert not notif.match_offer(job(is_active=False), pref())


def test_match_offer_no_criteria_matches_active_job():
    assert notif.match_offer(job(), pref())


def test_match_offer_min_salary_only_filters_offers_with_salary():
    p = pref(min_salary=400000)
    assert notif.match_offer(job(salary_range=None), p)  # pas de salaire affiché → pas filtrée
    assert notif.match_offer(job(salary_range="300 000 - 500 000 FCFA"), p)
    assert not notif.match_offer(job(salary_range="250 000 FCFA"), p)


@pytest.mark.parametrize("rng,expected", [
    ("300 000 - 500 000 FCFA", 500000), ("250000", 250000), (None, 0), ("À négocier", 0),
])
def test_max_salary(rng, expected):
    assert notif._max_salary(rng) == expected


def test_has_criteria():
    assert not notif._has_criteria(pref())
    assert not notif._has_criteria(pref(sectors=" | ", min_salary=0))
    assert notif._has_criteria(pref(keywords="python"))
    assert notif._has_criteria(pref(min_salary=100))


# ---------- match_offer_to_profile ----------
def test_match_offer_to_profile_by_sector_or_skills():
    prof = User_profiles(user_id="u1", sector="Informatique", skills="")
    assert notif.match_offer_to_profile(job(), prof)
    prof2 = User_profiles(user_id="u1", sector="Santé", skills="Go, fastapi, R")
    assert notif.match_offer_to_profile(job(), prof2)
    prof3 = User_profiles(user_id="u1", sector="Santé", skills="R, Go, infirmier")
    assert not notif.match_offer_to_profile(job(), prof3)  # compétences < 3 lettres ignorées


@pytest.mark.parametrize("raw,expected", [
    ("0749109013", "+2250749109013"),
    ("07 49 10 90 13", "+2250749109013"),
    ("+221771234567", "+221771234567"),
    ("00221771234567", "+221771234567"),
    ("2250749109013", "+2250749109013"),
    ("", ""),
])
def test_normalize_phone(raw, expected):
    assert notif._normalize_phone(raw) == expected


def test_placeholder_emails():
    assert notif._is_placeholder_email("")
    assert notif._is_placeholder_email("x@demo.com")
    assert notif._is_placeholder_email("browser_123@foo.com")
    assert not notif._is_placeholder_email("awa@gmail.com")


# ---------- dispatch_new_offer_alerts (intégration DB, envois mockés) ----------
@pytest.fixture
def sent(monkeypatch):
    calls: List[dict] = []

    async def fake_email(to, subject, html):
        calls.append({"type": "email", "to": to, "subject": subject})
        return True

    async def fake_whatsapp(to, body, params=None):
        calls.append({"type": "whatsapp", "to": to})
        return True

    monkeypatch.setattr(notif, "send_email", fake_email)
    monkeypatch.setattr(notif, "send_whatsapp", fake_whatsapp)
    return calls


@pytest.fixture
def smtp_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    monkeypatch.setenv("SMTP_USER", "bot")
    monkeypatch.setenv("SMTP_PASSWORD", "x")


async def _seed(db, *, profile_email="awa@gmail.com", pref_kwargs=None):
    db.add(User_profiles(user_id="u1", full_name="Awa Koné", email=profile_email, cv_analyzed=True,
                         skills="python, sql", sector="Informatique / Tech", location="Abidjan"))
    db.add(Job_offers(title="Développeur Python", company="Wave", sector="Informatique / Tech",
                      location="Abidjan, Côte d'Ivoire", contract_type="CDI", is_active=True))
    db.add(Job_offers(title="Infirmier", company="Clinique", sector="Santé",
                      location="Dakar, Sénégal", contract_type="CDD", is_active=True))
    db.add(Job_offers(title="Data analyst", company="Orange", sector="Informatique / Tech",
                      location="Abidjan", contract_type="CDI", is_active=False))
    if pref_kwargs is not None:
        db.add(Alert_preferences(user_id="u1", **pref_kwargs))
    await db.commit()


async def _notifs(db):
    return (await db.execute(select(Notification).where(Notification.user_id == "u1"))).scalars().all()


async def test_dispatch_with_pipe_preferences_and_dedup(db_session, sent, smtp_configured):
    await _seed(db_session, pref_kwargs=dict(sectors="Finance / Banque|Informatique / Tech", is_active=True))
    created = await notif.dispatch_new_offer_alerts()
    assert created == 1
    rows = await _notifs(db_session)
    assert len(rows) == 1 and "Développeur Python" in rows[0].title
    assert rows[0].channels == "in_app,email"
    assert [c["type"] for c in sent] == ["email"]

    # 2ᵉ passe : déjà notifié → rien de nouveau.
    assert await notif.dispatch_new_offer_alerts() == 0
    assert len(sent) == 1


async def test_dispatch_without_smtp_is_in_app_only(db_session, sent):
    await _seed(db_session, pref_kwargs=dict(keywords="python"))
    assert await notif.dispatch_new_offer_alerts() == 1
    assert (await _notifs(db_session))[0].channels == "in_app"
    assert sent == []


async def test_dispatch_skips_paused_alerts(db_session, sent, smtp_configured):
    await _seed(db_session, pref_kwargs=dict(sectors="Informatique / Tech", is_active=False))
    assert await notif.dispatch_new_offer_alerts() == 0
    assert sent == []


async def test_dispatch_email_opt_out_and_placeholder(db_session, sent, smtp_configured):
    await _seed(db_session, profile_email="x@demo.com", pref_kwargs=dict(keywords="python"))
    assert await notif.dispatch_new_offer_alerts() == 1
    assert sent == []  # adresse de démo jamais emailée


async def test_dispatch_falls_back_to_profile_without_explicit_criteria(db_session, sent):
    await _seed(db_session)  # pas de préférences → secteur/compétences du profil
    assert await notif.dispatch_new_offer_alerts() == 1
    assert "Développeur Python" in (await _notifs(db_session))[0].title


async def test_dispatch_ignores_profiles_without_analyzed_cv(db_session, sent):
    db_session.add(User_profiles(user_id="u1", email="awa@gmail.com", cv_analyzed=False, sector="Informatique / Tech"))
    db_session.add(Job_offers(title="Dev", company="X", sector="Informatique / Tech", is_active=True))
    await db_session.commit()
    assert await notif.dispatch_new_offer_alerts() == 0
