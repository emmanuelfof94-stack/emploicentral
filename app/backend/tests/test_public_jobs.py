"""Pages d'offres publiques (routers/public_jobs.py)."""
from __future__ import annotations

from datetime import date, timedelta

from models.job_offers import Job_offers
from models.job_postings import Job_postings
from routers import public_jobs

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=10)).isoformat()
PAST = (TODAY - timedelta(days=1)).isoformat()


async def _offer(db, **kw):
    base = dict(title="Comptable", company="Orange", location="Abidjan, Côte d'Ivoire",
                contract_type="CDI", description="Tenue des comptes", is_active=True, source="Emploi.ci")
    base.update(kw)
    job = Job_offers(**base)
    db.add(job)
    await db.commit()
    return job.id


async def test_list_returns_only_active_unexpired(client, db_session):
    live_ids = {
        await _offer(db_session, title="Actif sans échéance"),
        await _offer(db_session, title="Actif échéance future", valid_through=FUTURE),
        await _offer(db_session, title="Actif échéance aujourd'hui", valid_through=TODAY.isoformat()),
        await _offer(db_session, title="is_active NULL", is_active=None),
        await _offer(db_session, title="valid_through vide", valid_through=""),
    }
    await _offer(db_session, title="Expirée", valid_through=PAST)
    await _offer(db_session, title="Inactive", is_active=False)

    r = await client.get("/api/v1/public/jobs")
    assert r.status_code == 200
    body = r.json()
    assert {j["id"] for j in body["items"]} == live_ids
    assert body["total"] == len(live_ids)
    assert all(j["expired"] is False for j in body["items"])


async def test_list_is_public_and_excludes_pending_recruiter_offer(client, db_session):
    # Flux recruteur : l'offre est créée inactive tant qu'elle n'est pas approuvée.
    job_id = await _offer(db_session, title="Offre recruteur en attente", is_active=False)
    db_session.add(Job_postings(job_id=job_id, posted_by="rec-1", status="pending"))
    await db_session.commit()
    r = await client.get("/api/v1/public/jobs")  # sans token
    assert r.status_code == 200
    assert job_id not in {j["id"] for j in r.json()["items"]}


async def test_list_search_and_pagination(client, db_session):
    for i in range(3):
        await _offer(db_session, title=f"Développeur {i}", company="Wave")
    await _offer(db_session, title="Chauffeur", company="Bolloré")
    r = await client.get("/api/v1/public/jobs", params={"q": "wave", "limit": 2})
    body = r.json()
    assert body["total"] == 3 and len(body["items"]) == 2
    r2 = await client.get("/api/v1/public/jobs", params={"q": "wave", "limit": 2, "offset": 2})
    assert len(r2.json()["items"]) == 1


async def test_list_sorted_by_recency(client, db_session):
    old = await _offer(db_session, title="Ancienne", posted_date=(TODAY - timedelta(days=20)).isoformat())
    new = await _offer(db_session, title="Récente", posted_date=(TODAY - timedelta(days=1)).isoformat())
    ids = [j["id"] for j in (await client.get("/api/v1/public/jobs")).json()["items"]]
    assert ids.index(new) < ids.index(old)


async def test_list_decodes_html_entities(client, db_session):
    await _offer(db_session, title="Chargé d&#039;affaires", company="Soci&amp;t&eacute;")
    item = (await client.get("/api/v1/public/jobs")).json()["items"][0]
    assert item["title"] == "Chargé d'affaires"


async def test_detail_404_for_unapproved_recruiter_posting(client, db_session):
    for status in ("pending", "rejected"):
        job_id = await _offer(db_session, title=f"Recruteur {status}", is_active=True)
        db_session.add(Job_postings(job_id=job_id, posted_by="rec-1", status=status))
        await db_session.commit()
        r = await client.get(f"/api/v1/public/jobs/{job_id}")
        assert r.status_code == 404, status


async def test_detail_ok_for_approved_recruiter_and_aggregated_offer(client, db_session):
    approved = await _offer(db_session, title="Recruteur approuvée")
    db_session.add(Job_postings(job_id=approved, posted_by="rec-1", status="approved"))
    await db_session.commit()
    aggregated = await _offer(db_session, title="Agrégée")
    for job_id in (approved, aggregated):
        r = await client.get(f"/api/v1/public/jobs/{job_id}")
        assert r.status_code == 200 and r.json()["id"] == job_id


async def test_detail_expired_offer_is_flagged(client, db_session):
    job_id = await _offer(db_session, valid_through=PAST)
    r = await client.get(f"/api/v1/public/jobs/{job_id}")
    assert r.status_code == 200 and r.json()["expired"] is True


async def test_detail_unknown_is_404(client):
    assert (await client.get("/api/v1/public/jobs/999999")).status_code == 404


async def test_sitemap_lists_indexable_offers_only(client, db_session):
    live = await _offer(db_session, title="Live")
    linkedin = await _offer(db_session, title="LinkedIn", source="LinkedIn")
    expired = await _offer(db_session, title="Expirée", valid_through=PAST)
    xml = (await client.get("/sitemap.xml")).text
    assert f"/offres/{live}<" in xml
    assert f"/offres/{linkedin}<" not in xml
    assert f"/offres/{expired}<" not in xml


# ---------- JSON-LD Google for Jobs ----------
GOOGLE_REQUIRED = ("title", "description", "datePosted", "hiringOrganization", "jobLocation")


def _job(**kw):
    base = dict(id=7, title="Comptable", company="Orange", location="Abidjan, Côte d'Ivoire",
                contract_type="CDI", description="Tenue des comptes\nReporting", requirements="BAC+3",
                posted_date="2026-10-01", valid_through="2026-12-31", is_active=True)
    base.update(kw)
    return Job_offers(**base)


def test_jsonld_has_google_required_fields():
    data = public_jobs._job_posting_jsonld(_job())
    for field in GOOGLE_REQUIRED:
        assert data.get(field), field
    assert data["@type"] == "JobPosting"
    assert data["hiringOrganization"] == {"@type": "Organization", "name": "Orange"}
    assert data["jobLocation"]["address"] == {
        "@type": "PostalAddress", "addressCountry": "CI", "addressLocality": "Abidjan"}
    assert data["datePosted"] == "2026-10-01"
    assert data["validThrough"] == "2026-12-31T23:59:59"
    assert data["employmentType"] == "FULL_TIME"
    assert data["description"] == "<p>Tenue des comptes<br>Reporting</p><p>BAC+3</p>"
    assert data["url"].endswith("/offres/7")


def test_jsonld_minimal_offer_still_has_required_fields():
    job = _job(description=None, requirements=None, posted_date=None, valid_through=None,
               location=None, contract_type="Non précisé", title="Chef <b>de</b> projet")
    data = public_jobs._job_posting_jsonld(job)
    for field in GOOGLE_REQUIRED:
        assert data.get(field), field
    assert "<b>" not in data["description"]           # titre échappé en repli
    assert data["jobLocation"]["address"]["addressCountry"] == "CI"
    assert "validThrough" not in data and "employmentType" not in data


def test_jsonld_country_code_from_location():
    data = public_jobs._job_posting_jsonld(_job(location="Dakar, Sénégal"))
    assert data["jobLocation"]["address"] == {
        "@type": "PostalAddress", "addressCountry": "SN", "addressLocality": "Dakar"}


def test_jsonld_escapes_html_in_description():
    data = public_jobs._job_posting_jsonld(_job(description="<script>alert(1)</script>"))
    assert "<script>" not in data["description"]
