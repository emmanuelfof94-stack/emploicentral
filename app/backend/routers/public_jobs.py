"""
Pages d'offres PUBLIQUES (sans compte) + référencement Google for Jobs.

- API JSON : `GET /api/v1/public/jobs` (liste) et `GET /api/v1/public/jobs/{id}`.
- HTML : `GET /offres` et `GET /offres/{id}` servent l'index.html du SPA avec un
  <head> enrichi côté serveur (titre, description, canonical, Open Graph) et, pour
  une offre active, le JSON-LD `JobPosting` lu par Google for Jobs. Le SPA prend
  ensuite le relais pour l'affichage.
- `GET /sitemap.xml` dynamique : pages publiques + chaque offre active.

Les routes HTML n'existent qu'en déploiement « tout-en-un » (dossier `static/`) ;
en dev local, Vite sert le front et ces URL tombent sur le SPA directement.
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime
from functools import lru_cache
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.job_offers import Job_offers
from models.job_postings import Job_postings

router = APIRouter(tags=["public"])

SITE_URL = (os.environ.get("PUBLIC_SITE_URL") or "https://emploicentral.onrender.com").rstrip("/")
INDEX_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "index.html")


# ---------- Schemas ----------
class PublicJob(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None
    contract_type: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    posted_date: Optional[str] = None
    valid_through: Optional[str] = None
    expired: bool = False


class PublicJobList(BaseModel):
    items: List[PublicJob]
    total: int


# ---------- Helpers ----------
def _today() -> str:
    return date.today().isoformat()


def _text(value: Optional[str]) -> Optional[str]:
    """Décode les entités HTML laissées par certaines sources (ex. `&#039;`)."""
    return html.unescape(html.unescape(value)) if value else value


def _is_live(job: Job_offers) -> bool:
    if job.is_active is False:
        return False
    return not (job.valid_through and job.valid_through < _today())


# Sources sans contenu propre (ajout manuel, texte générique) : visibles sur le site
# mais pas proposées à Google (contenu « mince » qui pénaliserait tout le domaine).
_NON_INDEXABLE_SOURCES = {"LinkedIn"}


def _indexable(job: Job_offers) -> bool:
    return _is_live(job) and (job.source or "") not in _NON_INDEXABLE_SOURCES


def _to_public(job: Job_offers) -> PublicJob:
    return PublicJob(
        id=job.id, title=_text(job.title), company=_text(job.company), location=job.location,
        contract_type=job.contract_type, sector=job.sector, description=_text(job.description),
        requirements=_text(job.requirements), salary_range=job.salary_range, source=job.source,
        source_url=job.source_url, posted_date=job.posted_date, valid_through=job.valid_through,
        expired=not _is_live(job),
    )


async def _load_public(db: AsyncSession, job_id: int) -> Optional[Job_offers]:
    """L'offre si elle est publiable : jamais une offre recruteur non approuvée."""
    job = (await db.execute(select(Job_offers).where(Job_offers.id == job_id))).scalars().first()
    if not job:
        return None
    posting = (await db.execute(select(Job_postings).where(Job_postings.job_id == job_id))).scalars().first()
    if posting and posting.status != "approved":
        return None
    return job


def _live_filter(stmt):
    return stmt.where(
        or_(Job_offers.is_active.is_(None), Job_offers.is_active.is_(True)),
        or_(Job_offers.valid_through.is_(None), Job_offers.valid_through == "",
            Job_offers.valid_through >= _today()),
    )


# Type de contrat (libellé canonique de l'agrégateur) → enum schema.org.
_EMPLOYMENT_TYPES = {
    "CDI": "FULL_TIME",
    "CDD": "TEMPORARY",
    "Stage": "INTERN",
    "Alternance": "INTERN",
    "Freelance": "CONTRACTOR",
    "Temps partiel": "PART_TIME",
}

# Pays (tel qu'écrit dans `location`, ex. "Abidjan, Côte d'Ivoire") → code ISO.
_COUNTRIES = {
    "côte d'ivoire": "CI", "cote d'ivoire": "CI", "sénégal": "SN", "senegal": "SN",
    "togo": "TG", "bénin": "BJ", "benin": "BJ", "mali": "ML", "burkina faso": "BF",
    "guinée": "GN", "niger": "NE", "cameroun": "CM", "ghana": "GH",
}


def _address(location: Optional[str]) -> dict:
    parts = [p.strip() for p in (location or "").split(",") if p.strip()]
    country = "CI"  # marché principal par défaut
    locality = None
    if parts:
        code = _COUNTRIES.get(parts[-1].lower())
        if code:
            country = code
            parts = parts[:-1]
        locality = parts[0] if parts else None
    addr = {"@type": "PostalAddress", "addressCountry": country}
    if locality:
        addr["addressLocality"] = locality
    return addr


def _iso_date(value) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    return None


def _job_posting_jsonld(job: Job_offers) -> dict:
    """JSON-LD `JobPosting` (https://developers.google.com/search/docs/appearance/structured-data/job-posting)."""
    body = []
    for block in (_text(job.description), _text(job.requirements)):
        if block and block.strip():
            body.append("<p>" + html.escape(block.strip()).replace("\n", "<br>") + "</p>")
    data = {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "title": _text(job.title),
        "description": "".join(body) or html.escape(job.title),
        "datePosted": _iso_date(job.posted_date) or _iso_date(job.created_at) or _today(),
        "hiringOrganization": {"@type": "Organization", "name": _text(job.company)},
        "jobLocation": {"@type": "Place", "address": _address(job.location)},
        "identifier": {"@type": "PropertyValue", "name": "EmploiCentral", "value": str(job.id)},
        "directApply": False,
        "url": f"{SITE_URL}/offres/{job.id}",
    }
    if job.valid_through:
        data["validThrough"] = f"{job.valid_through[:10]}T23:59:59"
    employment = _EMPLOYMENT_TYPES.get((job.contract_type or "").strip())
    if employment:
        data["employmentType"] = employment
    return data


@lru_cache(maxsize=1)
def _index_template() -> str:
    with open(INDEX_HTML, encoding="utf-8") as fh:
        return fh.read()


def _render_index(title: str, description: str, url: str, jsonld: Optional[dict] = None,
                  noindex: bool = False) -> HTMLResponse:
    """index.html du SPA avec un <head> propre à la page (SEO + aperçu de partage)."""
    try:
        page = _index_template()
    except OSError:
        raise HTTPException(status_code=404, detail="Not Found")
    t, d, u = html.escape(title), html.escape(description), html.escape(url)
    page = re.sub(r"<title>.*?</title>", f"<title>{t}</title>", page, count=1, flags=re.S)
    for attr, val in (('name="description"', d), ('property="og:title"', t),
                      ('property="og:description"', d), ('property="og:url"', u),
                      ('name="twitter:title"', t), ('name="twitter:description"', d)):
        page = re.sub(rf'<meta {attr} content="[^"]*"\s*/?>', f'<meta {attr} content="{val}" />', page, count=1)
    page = re.sub(r'<link rel="canonical" href="[^"]*"\s*/?>', f'<link rel="canonical" href="{u}" />', page, count=1)
    extra = ""
    if noindex:
        extra += '<meta name="robots" content="noindex" />\n'
    if jsonld:
        # "</" échappé pour qu'aucune donnée ne puisse fermer la balise <script>.
        payload = json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")
        extra += f'<script type="application/ld+json">{payload}</script>\n'
    if extra:
        page = page.replace("</head>", extra + "</head>", 1)
    return HTMLResponse(page)


def _summary(job: Job_offers) -> str:
    bits = [_text(job.company), job.location, job.contract_type if job.contract_type != "Non précisé" else None]
    lead = " · ".join(b for b in bits if b)
    desc = re.sub(r"\s+", " ", _text(job.description) or "").strip()
    text = f"{lead} — {desc}" if desc else lead
    return text[:157] + "…" if len(text) > 160 else text


# ---------- API JSON ----------
@router.get("/api/v1/public/jobs", response_model=PublicJobList)
async def list_public_jobs(
    q: Optional[str] = Query(None, max_length=100),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = _live_filter(select(Job_offers))
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Job_offers.title.ilike(like), Job_offers.company.ilike(like),
                              Job_offers.location.ilike(like), Job_offers.sector.ilike(like)))
    # Date de publication, à défaut date d'entrée en base (sinon Postgres trie les NULL en tête).
    recency = func.coalesce(Job_offers.posted_date, func.substr(cast(Job_offers.created_at, String), 1, 10))
    rows = (await db.execute(stmt.order_by(recency.desc(), Job_offers.id.desc()))).scalars().all()
    return PublicJobList(items=[_to_public(j) for j in rows[offset:offset + limit]], total=len(rows))


@router.get("/api/v1/public/jobs/{job_id}", response_model=PublicJob)
async def get_public_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _load_public(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    return _to_public(job)


# ---------- Pages HTML (SEO) ----------
@router.get("/offres", response_class=HTMLResponse, include_in_schema=False)
async def offers_page():
    return _render_index(
        "Offres d'emploi en Côte d'Ivoire et Afrique de l'Ouest | EmploiCentral",
        "Consultez les dernières offres d'emploi à Abidjan, en Côte d'Ivoire et en Afrique de l'Ouest : "
        "CDI, CDD, stages. Mises à jour plusieurs fois par jour.",
        f"{SITE_URL}/offres",
    )


@router.get("/offres/{job_id}", response_class=HTMLResponse, include_in_schema=False)
async def offer_page(job_id: int, db: AsyncSession = Depends(get_db)):
    job = await _load_public(db, job_id)
    url = f"{SITE_URL}/offres/{job_id}"
    if not job:
        return _render_index("Offre introuvable | EmploiCentral", "Cette offre n'existe pas ou plus.", url, noindex=True)
    title = f"{_text(job.title)} — {_text(job.company)}" + (f" ({job.location.split(',')[0]})" if job.location else "")
    indexable = _indexable(job)
    # Offre expirée (ou source non indexable) : page conservée pour les liens partagés,
    # mais sans JSON-LD et hors index.
    return _render_index(f"{title} | EmploiCentral", _summary(job), url,
                         jsonld=_job_posting_jsonld(job) if indexable else None, noindex=not indexable)


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(_live_filter(select(Job_offers)).order_by(Job_offers.id.desc()))).scalars().all()
    urls = [
        (f"{SITE_URL}/", None, "daily", "1.0"),
        (f"{SITE_URL}/offres", _today(), "hourly", "0.9"),
        (f"{SITE_URL}/recruiter/signup", None, "monthly", "0.7"),
        (f"{SITE_URL}/login", None, "monthly", "0.5"),
    ]
    for job in rows:
        if not _indexable(job):
            continue
        lastmod = _iso_date(job.updated_at) or _iso_date(job.posted_date)
        urls.append((f"{SITE_URL}/offres/{job.id}", lastmod, "weekly", "0.8"))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod, freq, prio in urls:
        lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
        lines.append(f"  <url><loc>{html.escape(loc)}</loc>{lm}<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    lines.append("</urlset>")
    return Response("\n".join(lines), media_type="application/xml")
