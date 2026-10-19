"""Reclassement versionné des secteurs + complétion des descriptions (job_aggregator)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from models.app_markers import App_markers
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from services import job_aggregator as agg


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(agg, "_sectors_reclassified", False)
    monkeypatch.setattr(agg, "_enrich_attempted", set())


async def _offer(db, title, sector, source="Emploi.ci", description="", url=None):
    job = Job_offers(title=title, company="ACME", sector=sector, source=source,
                     description=description, source_url=url, is_active=True)
    db.add(job)
    await db.commit()
    return job.id


async def test_full_pass_once_per_rules_version(db_session):
    wrong = await _offer(db_session, "Frigoriste carrosserie", "Énergie / Mines")
    recruiter_job = await _offer(db_session, "Comptable", "Marketing / Communication")
    db_session.add(Job_postings(job_id=recruiter_job, posted_by="u1", company_name="ACME", status="approved"))
    await db_session.commit()

    assert await agg.reclassify_sectors() == 1
    marker = await db_session.get(App_markers, "sector_rules_version")
    assert marker.value == agg.SECTOR_RULES_VERSION
    rows = {j.id: j for j in (await db_session.execute(select(Job_offers))).scalars().all()}
    for j in rows.values():
        await db_session.refresh(j)
    assert rows[wrong].sector == "Industrie"
    assert rows[recruiter_job].sector == "Marketing / Communication"  # choix du recruteur respecté


async def test_no_full_pass_when_marker_is_current(db_session, monkeypatch):
    db_session.add(App_markers(key="sector_rules_version", value=agg.SECTOR_RULES_VERSION))
    await db_session.commit()
    kept = await _offer(db_session, "Frigoriste carrosserie", "Énergie / Mines")  # canonique : non retouché
    raw = await _offer(db_session, "Comptable", "Services autres")              # libellé brut : reclassé
    assert await agg.reclassify_sectors() == 1
    by_id = {j.id: j for j in (await db_session.execute(select(Job_offers))).scalars().all()}
    for j in by_id.values():
        await db_session.refresh(j)
    assert by_id[kept].sector == "Énergie / Mines"
    assert by_id[raw].sector == "Comptabilité / Audit"


@pytest.mark.parametrize("title,expected", [
    ("Frigoriste Carrosserie", "Industrie"),
    ("Support administratif Travel & Expenses", "Administration / Secrétariat"),
    ("Programmateur Musical Azawan", "Marketing / Communication"),
    ("Video Editor", "Marketing / Communication"),
    ("Robotics Engineer (Remote)", "Informatique / Tech"),
    ("L'Africaine de la Main d'œuvre recrute Gestionnaires des stocks", "Logistique / Transport"),
    ("Technicien en Génie Civil", "BTP / Construction"),
    ("Stagiaire Business Developer (H/F)", "Commerce / Vente"),
])
def test_refined_sector_rules(title, expected):
    assert agg.normalize_sector(None, title, "") == expected


async def test_enrichment_commits_each_offer(db_session, monkeypatch):
    long_body = "<p>" + "Missions principales du poste. " * 30 + "</p>"
    ok = await _offer(db_session, "Comptable", "Autres", source="AfriqueEmplois",
                      description="court", url="https://afriqueemplois.com/ci/post/1")
    broken = await _offer(db_session, "Juriste", "Juridique", source="AfriqueEmplois",
                          description="court", url="https://afriqueemplois.com/ci/post/2")

    async def fake_fetch(client, url, *a, **k):
        if url.endswith("/1"):
            return f'<div class="prose max-w-none">{long_body}</div>'
        return "<html>pas de contenu</html>"

    monkeypatch.setattr(agg, "_fetch", fake_fetch)
    monkeypatch.setattr(agg.asyncio, "sleep", _no_sleep)
    assert await agg.enrich_short_descriptions(client=None) == 1
    jobs = {j.id: j for j in (await db_session.execute(select(Job_offers))).scalars().all()}
    for j in jobs.values():
        await db_session.refresh(j)
    assert len(jobs[ok].description) > 400 and jobs[ok].sector == "Comptabilité / Audit"
    assert jobs[broken].description == "court"


async def _no_sleep(*_a, **_k):
    return None
