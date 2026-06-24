"""
Agrégateur d'offres d'emploi externes (multi-sources).

Récupère périodiquement les offres publiées sur des sites externes et les insère
dans la table `job_offers`, en évitant les doublons.

Sources actuelles (voir SOURCES):
- Emploi.ci  (Côte d'Ivoire)
- Emploi.sn  (Sénégal — même plateforme "Emploi Group" qu'Emploi.ci)
- Novojob    (Côte d'Ivoire)

Toutes ces sources exposent un JSON-LD schema.org `JobPosting` sur leurs pages
détail, donc le même parseur est réutilisé pour toutes. Ajouter une source =
ajouter une entrée dans SOURCES (URL de liste, motif des liens d'offre, motif
d'extraction de l'identifiant externe).

Politesse / légalité:
- robots.txt des sites autorise `User-agent: *` (les `Disallow: /` ne visent que
  des bots d'IA). On utilise un User-Agent identifiable, NON déguisé en bot d'IA,
  et on insère un court délai entre chaque page détail.
- Seules les pages déjà présentes (par identifiant externe) sont ignorées, ce qui
  limite aussi le nombre de requêtes.

Compatible Python 3.9 (typing explicite, pas de PEP 604 `X | Y`).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Pattern

import httpx

from core.database import db_manager
from services.job_offers import Job_offersService

logger = logging.getLogger(__name__)

USER_AGENT = "EmploiCentralBot/1.0 (+job offer aggregator; contact: admin)"

# --------------------------------------------------------------------------- #
# Définition des sources
# --------------------------------------------------------------------------- #
# Chaque source:
#   name         : valeur stockée dans job_offers.source
#   base         : origine HTTP (sans slash final)
#   listing_path : chemin de la page de liste
#   offer_re     : motif d'un chemin d'offre (cherché dans le HTML de la liste)
#   id_re        : motif d'extraction de l'identifiant externe depuis l'URL
#   paginate     : True si la liste accepte ?page=N
SOURCES: List[Dict[str, object]] = [
    {
        "name": "Emploi.ci",
        "base": "https://www.emploi.ci",
        "listing_path": "/recherche-jobs-cote-ivoire",
        "offer_re": re.compile(r"/offre-emploi-cote-ivoire/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Emploi.sn",
        "base": "https://www.emploi.sn",
        "listing_path": "/recherche-jobs-senegal",
        "offer_re": re.compile(r"/offre-emploi-senegal/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Novojob",
        "base": "https://www.novojob.com",
        "listing_path": "/cote-d-ivoire/offres-d-emploi",
        # ex: /cote-d-ivoire/offres-d-emploi/offre-d-emploi/cote-d-ivoire/136656-assistant-...
        "offer_re": re.compile(r"/[a-z-]+/offres-d-emploi/offre-d-emploi/[a-z-]+/\d+-[a-z0-9-]+", re.I),
        "id_re": re.compile(r"/(\d+)-[a-z0-9-]+"),
        "paginate": False,
    },
    {
        # La page pays embarque un ItemList JSON-LD avec ~10 JobPosting complets :
        # une seule requête suffit, pas besoin de crawler les pages détail.
        "name": "AfriqueEmplois",
        "base": "https://afriqueemplois.com",
        "listing_path": "/ci",
        "mode": "listing_jsonld",
        "id_re": re.compile(r"/post/(\d+)"),
        "paginate": False,
    },
    {
        # Tectra (intérim/recrutement, Maroc) : job board sur la plateforme SaaS
        # CVParser (SPA Angular) adossée à une API JSON. On consomme directement
        # l'API `/annonces?p=N` (pagination 0-indexée, ~10 offres/page).
        "name": "Tectra",
        "mode": "cvparser_api",
        "api_base": "https://tectra-offres.cvparser.ma/cvpmini-be/api",
        "detail_base": "https://talent-tectra.com/s3/annonce",
        "company": "Tectra",
        "id_re": re.compile(r"/annonce/(\d+)"),
        "paginate": True,
    },
]

_LDJSON_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


# --------------------------------------------------------------------------- #
# Configuration runtime (env, avec défauts raisonnables)
# --------------------------------------------------------------------------- #
def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _cfg_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def aggregator_enabled() -> bool:
    return _cfg_bool("AGGREGATOR_ENABLED", True)


def interval_minutes() -> int:
    return max(5, _cfg_int("AGGREGATOR_INTERVAL_MINUTES", 360))


def max_per_run() -> int:
    """Nb max de nouvelles offres insérées par exécution ET PAR SOURCE."""
    return max(1, _cfg_int("AGGREGATOR_MAX_PER_RUN", 20))


def listing_pages() -> int:
    return max(1, _cfg_int("AGGREGATOR_PAGES", 1))


def _enabled_source_names() -> Optional[set]:
    """Filtre optionnel: AGGREGATOR_SOURCES="Emploi.ci,Novojob" (None = toutes)."""
    raw = os.environ.get("AGGREGATOR_SOURCES")
    if not raw:
        return None
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


# --------------------------------------------------------------------------- #
# Récupération / parsing
# --------------------------------------------------------------------------- #
def _extract_external_id(url: str, id_re: Pattern) -> Optional[str]:
    m = id_re.search(url or "")
    return m.group(1) if m else None


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", text or "")).strip()


# Canonical contract types. Order matters only for matching keys; the earliest
# match found in the raw string wins. Keys are matched case-insensitively.
_CONTRACT_RULES = [
    ("alternance", "Alternance"),
    ("apprentissage", "Alternance"),
    ("intern", "Stage"),          # schema.org INTERN
    ("stage", "Stage"),
    ("intérim", "Intérim"),
    ("interim", "Intérim"),
    ("temporary", "Intérim"),     # schema.org TEMPORARY
    ("freelance", "Freelance"),
    ("contractor", "Freelance"),  # schema.org CONTRACTOR
    ("temps partiel", "Temps partiel"),
    ("part_time", "Temps partiel"),
    ("part time", "Temps partiel"),
    ("cdd", "CDD"),
    ("cdi", "CDI"),
    ("full_time", "CDI"),         # schema.org FULL_TIME
    ("full time", "CDI"),
    ("temps plein", "CDI"),
    ("statutaire", "CDI"),
]

# If a raw value contains this many or more distinct contract types, it's almost
# certainly the site's filter list scraped by mistake → treat as unspecified.
_CONTRACT_GARBAGE_THRESHOLD = 4


def normalize_contract_type(raw: Optional[str]) -> str:
    """Map a raw employmentType string to a single canonical French contract type.

    Handles clean values (CDI), schema.org enums (FULL_TIME, PART_TIME), and
    multi-value strings ("CDI - CDD"). Returns "Non précisé" when empty or when
    the value looks like a full filter list (too many types)."""
    if not raw or not str(raw).strip():
        return "Non précisé"
    low = str(raw).lower()
    found = []  # (index_in_string, label)
    seen_labels = set()
    for key, label in _CONTRACT_RULES:
        pos = low.find(key)
        if pos >= 0 and label not in seen_labels:
            seen_labels.add(label)
            found.append((pos, label))
    if not found:
        return "Non précisé"
    if len(found) >= _CONTRACT_GARBAGE_THRESHOLD:
        return "Non précisé"
    found.sort(key=lambda x: x[0])
    return found[0][1]


# Canonical sectors with keyword rules (ordered by priority — first hit wins).
# Used both to consolidate scraped labels and to INFER a sector from the job
# title/description when the source provides none.
_SECTOR_RULES = [
    (["fintech", "paiement mobile", "mobile money", "monétique"], "Fintech"),
    (["télécom", "telecom", "télécommunication", "fibre optique", "gsm"], "Télécommunications"),
    (
        ["développeur", "developpeur", "logiciel", "software", "informatique", "technolog",
         "data", "devops", "programmation", "réseau informatique", "cybersécurité", "web"],
        "Informatique / Tech",
    ),
    (["comptab", "audit", "fiscal", "contrôle de gestion"], "Comptabilité / Audit"),
    (["banque", "bancaire", "finance", "crédit", "microfinance", "assurance"], "Finance / Banque"),
    (["marketing", "communication", "community manager", "seo", "publicité", "média", "contenu"],
     "Marketing / Communication"),
    (["logistique", "supply chain", "transport", "approvisionnement", "fret", "douane",
      "import-export", "magasinier"], "Logistique / Transport"),
    (["btp", "construction", "génie civil", "chantier", "bâtiment", "immobilier", "architecte", "travaux"],
     "BTP / Construction"),
    (["commercial", "vente", "business development", "négociation", "télévente", "sales", "caissier"],
     "Commerce / Vente"),
    (["ressources humaines", "recrutement", "paie", "talent"], "Ressources Humaines"),
    (["santé", "médical", "infirmier", "médecin", "pharmac", "hôpital", "soignant"], "Santé"),
    (["enseign", "formation", "pédagog", "éducation", "professeur", "formateur"], "Éducation / Formation"),
    (["juridique", "avocat", "juriste", "droit "], "Juridique"),
    (["agro", "agricole", "agriculture", "élevage", "agronome"], "Agroalimentaire / Agriculture"),
    (["industrie", "production", "usine", "manufactur", "maintenance", "mécanique", "électricité", "ingénieur"],
     "Industrie"),
    (["hôtel", "restauration", "tourisme", "accueil"], "Hôtellerie / Tourisme"),
]


_APOS_RE = re.compile(r"[`´’']")

_COUNTRY_RULES = [
    (["côte d'ivoire", "cote d'ivoire", "cote d ivoire", "côte d ivoire"], "Côte d'Ivoire"),
    (["sénégal", "senegal"], "Sénégal"),
    (["burkina"], "Burkina Faso"),
    (["bénin", "benin"], "Bénin"),
    (["togo"], "Togo"),
    (["mali"], "Mali"),
    (["nigeria", "nigéria"], "Nigeria"),
    (["niger"], "Niger"),
    (["guinée", "guinea", "guinee"], "Guinée"),
    (["ghana"], "Ghana"),
    (["cameroun", "cameroon"], "Cameroun"),
    (["gabon"], "Gabon"),
    (["maroc"], "Maroc"),
    (["tunisie"], "Tunisie"),
    (["france"], "France"),
]

_ABIDJAN_DISTRICTS = [
    "cocody", "angré", "angre", "plateau", "yopougon", "marcory", "treichville",
    "koumassi", "abobo", "adjamé", "adjame", "bingerville", "port-bouët", "port-bouet",
    "riviera", "djorobité", "djorobite",
]

_CITY_RULES = [
    (["abidjan"] + _ABIDJAN_DISTRICTS, "Abidjan"),
    (["yamoussoukro"], "Yamoussoukro"),
    (["bouaké", "bouake"], "Bouaké"),
    (["san-pédro", "san pedro", "san-pedro"], "San-Pédro"),
    (["dakar"], "Dakar"),
    (["thiès", "thies"], "Thiès"),
    (["lomé", "lome"], "Lomé"),
    (["cotonou"], "Cotonou"),
    (["ouagadougou"], "Ouagadougou"),
    (["bamako"], "Bamako"),
    (["niamey"], "Niamey"),
    (["conakry"], "Conakry"),
    (["accra"], "Accra"),
    (["lagos"], "Lagos"),
    (["douala"], "Douala"),
    (["yaoundé", "yaounde"], "Yaoundé"),
    (["abuja"], "Abuja"),
]


def normalize_location(raw: Optional[str]) -> Optional[str]:
    """Consolidate a messy location string into a canonical "Ville, Pays" form,
    so all variants of the same place collapse to a single selectable value."""
    if not raw or not str(raw).strip():
        return None
    low = _APOS_RE.sub("'", str(raw).lower())

    country = None
    for keys, label in _COUNTRY_RULES:
        if any(k in low for k in keys):
            country = label
            break
    if country is None and re.search(r"\bci\b", low):
        country = "Côte d'Ivoire"

    city = None
    for keys, label in _CITY_RULES:
        if any(k in low for k in keys):
            city = label
            break

    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    if country:
        return country
    # Fallback: dedupe comma-separated parts, keep original.
    parts: List[str] = []
    for part in str(raw).split(","):
        t = part.strip()
        if t and t.lower() not in [x.lower() for x in parts]:
            parts.append(t)
    return ", ".join(parts) if parts else str(raw).strip()


def _classify_sector(text: str) -> Optional[str]:
    low = (text or "").lower()
    for keywords, label in _SECTOR_RULES:
        if any(k in low for k in keywords):
            return label
    return None


def normalize_sector(raw: Optional[str], title: str = "", description: str = "") -> Optional[str]:
    """Map a raw sector label to a canonical sector. If no usable label, infer one
    from the job title/description. Returns None only when nothing can be inferred."""
    raw_clean = (raw or "").strip()
    if raw_clean:
        hit = _classify_sector(raw_clean)
        if hit:
            return hit
        # Unknown but explicit label → keep it (cleaned) rather than lose information.
        return raw_clean
    # No source sector → infer, prioritising the title (more reliable than the
    # description, which often mentions incidental keywords like "outils informatiques").
    return _classify_sector(title) or _classify_sector(description)


async def _fetch(client: httpx.AsyncClient, url: str, retries: int = 2) -> Optional[str]:
    """GET avec reprises (certains sites comme Novojob sont intermittents)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            # 429/5xx: ça vaut le coup de réessayer; autres 4xx: inutile.
            if resp.status_code != 429 and resp.status_code < 500:
                logger.warning("Aggregator: %s -> HTTP %s", url, resp.status_code)
                return None
            last_err = "HTTP %s" % resp.status_code
        except httpx.HTTPError as exc:
            last_err = str(exc) or exc.__class__.__name__
        if attempt < retries:
            await asyncio.sleep(1.5 * (attempt + 1))  # backoff progressif
    logger.warning("Aggregator: échec requête %s après %d essais: %s", url, retries + 1, last_err)
    return None


def _page_url(source: Dict[str, object], page: int) -> Optional[str]:
    base = str(source["base"])
    path = str(source["listing_path"])
    if page <= 1:
        return base + path
    if not source.get("paginate"):
        return None
    return f"{base}{path}?page={page}"


async def _collect_listing_urls(client: httpx.AsyncClient, source: Dict[str, object], pages: int) -> List[str]:
    """Récupère les URLs d'offres (absolues) depuis une ou plusieurs pages de liste."""
    base = str(source["base"])
    offer_re: Pattern = source["offer_re"]  # type: ignore[assignment]
    seen: Dict[str, None] = {}
    for page in range(1, pages + 1):
        url = _page_url(source, page)
        if not url:
            break
        html = await _fetch(client, url)
        if not html:
            continue
        for path in offer_re.findall(html):
            full = path if path.startswith("http") else base + path
            seen.setdefault(full, None)
        await asyncio.sleep(0.5)
    return list(seen.keys())


def _find_job_postings(node: object, out: List[Dict[str, object]]) -> None:
    """Collecte récursivement tous les objets JobPosting (gère @graph / ItemList)."""
    if isinstance(node, dict):
        if node.get("@type") == "JobPosting":
            out.append(node)
        for v in node.values():
            _find_job_postings(v, out)
    elif isinstance(node, list):
        for v in node:
            _find_job_postings(v, out)


def _all_job_postings(html: str) -> List[Dict[str, object]]:
    """Tous les JobPosting trouvés dans les blocs JSON-LD de la page."""
    result: List[Dict[str, object]] = []
    for block in _LDJSON_RE.findall(html):
        try:
            data = json.loads(block.strip(), strict=False)
        except json.JSONDecodeError:
            continue
        _find_job_postings(data, result)
    return result


def _parse_job_posting(html: str) -> Optional[Dict[str, object]]:
    """Premier JobPosting d'une page détail (recherche en profondeur)."""
    found = _all_job_postings(html)
    return found[0] if found else None


def _map_to_offer(posting: Dict[str, object], source_url: str, source_name: str) -> Optional[Dict[str, object]]:
    """Transforme un JobPosting schema.org en ligne `job_offers`."""
    title = (posting.get("title") or "").strip() if isinstance(posting.get("title"), str) else ""
    if not title:
        return None

    org = posting.get("hiringOrganization") or {}
    company = ""
    if isinstance(org, dict):
        company = (org.get("name") or "").strip()
    elif isinstance(org, str):
        company = org.strip()

    loc = posting.get("jobLocation") or {}
    location = None
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
            location = ", ".join(p for p in parts if isinstance(p, str) and p.strip())
    location = normalize_location(location)

    raw_contract = posting.get("employmentType")
    if isinstance(raw_contract, list):
        raw_contract = ", ".join(str(x) for x in raw_contract)
    contract_type = normalize_contract_type(raw_contract)

    description = _strip_html(str(posting.get("description", "")))[:4000] or None
    requirements = _strip_html(str(posting.get("qualifications") or posting.get("experienceRequirements") or "")) or None

    industry = posting.get("industry")
    raw_sector = industry if isinstance(industry, str) else None
    sector = normalize_sector(raw_sector, title, description or "")

    salary_range = None
    base = posting.get("baseSalary")
    if isinstance(base, dict):
        value = base.get("value")
        if isinstance(value, dict):
            amt = value.get("value") or value.get("minValue")
            unit = value.get("unitText") or ""
            cur = base.get("currency") or ""
            if amt:
                salary_range = f"{amt} {cur} {unit}".strip()

    posted_date = None
    dp = posting.get("datePosted")
    if isinstance(dp, str) and dp:
        posted_date = dp[:10]  # partie date (YYYY-MM-DD)

    valid_through = None
    vt = posting.get("validThrough")
    if isinstance(vt, str) and vt:
        valid_through = vt[:10]  # date d'expiration (YYYY-MM-DD)

    # Une offre déjà expirée à l'insertion est créée inactive.
    today = datetime.now().strftime("%Y-%m-%d")
    is_active = not (valid_through and valid_through < today)

    return {
        "title": title[:255],
        "company": (company or "Non précisé")[:255],
        "location": location,
        "contract_type": contract_type,
        "sector": sector,
        "description": description,
        "requirements": requirements,
        "salary_range": salary_range,
        "source": source_name,
        "source_url": source_url,
        "posted_date": posted_date,
        "valid_through": valid_through,
        "is_active": is_active,
    }


async def _collect_listing_jsonld(
    client: httpx.AsyncClient, source: Dict[str, object], existing_ids: set, existing_urls: set, limit: int
) -> List[Dict[str, object]]:
    """Mode 'listing_jsonld': les offres sont déjà dans le JSON-LD de la page liste
    (ItemList de JobPosting). Une requête par page, pas de crawl des pages détail."""
    name = str(source["name"])
    base = str(source["base"])
    id_re: Pattern = source["id_re"]  # type: ignore[assignment]

    new_offers: List[Dict[str, object]] = []
    for page in range(1, listing_pages() + 1):
        url = _page_url(source, page)
        if not url:
            break
        html = await _fetch(client, url)
        await asyncio.sleep(0.5)
        if not html:
            continue
        postings = _all_job_postings(html)
        logger.info("Aggregator[%s]: %d offres dans la page liste", name, len(postings))
        for jp in postings:
            if len(new_offers) >= limit:
                break
            offer_url = str(jp.get("url") or "")
            if offer_url and not offer_url.startswith("http"):
                offer_url = base + offer_url
            if not offer_url or offer_url in existing_urls:
                continue
            ext_id = _extract_external_id(offer_url, id_re)
            if ext_id and ext_id in existing_ids:
                continue
            offer = _map_to_offer(jp, offer_url, name)
            if offer:
                new_offers.append(offer)
                existing_urls.add(offer_url)  # évite les doublons inter-pages dans la même passe
                if ext_id:
                    existing_ids.add(ext_id)
        if len(new_offers) >= limit:
            break
    return new_offers


def _map_cvparser_offer(
    o: Dict[str, object], offer_url: str, source_name: str, company: str
) -> Optional[Dict[str, object]]:
    """Transforme une annonce de l'API CVParser (`/annonces`) en ligne `job_offers`."""
    title = re.sub(r"\s+", " ", str(o.get("title") or "")).strip()
    if not title:
        return None

    city = o.get("city")
    location = normalize_location(city if isinstance(city, str) else None)
    contract_type = normalize_contract_type(o.get("contart"))

    raw_html = o.get("annonce_html_data") or o.get("content") or ""
    description = _strip_html(str(raw_html))[:4000] or None

    raw_sector = o.get("sector") if isinstance(o.get("sector"), str) else None
    sector = normalize_sector(raw_sector, title, description or "")

    reqs = []
    if o.get("exp"):
        reqs.append(f"Expérience : {str(o['exp']).strip()}")
    if o.get("formation"):
        reqs.append(f"Formation : {str(o['formation']).strip()}")
    requirements = " · ".join(reqs) or None

    posted_date = None
    dt = o.get("date")
    if isinstance(dt, str) and dt:
        posted_date = dt[:10]  # "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DD"

    return {
        "title": title[:255],
        "company": (company or "Non précisé")[:255],
        "location": location,
        "contract_type": contract_type,
        "sector": sector,
        "description": description,
        "requirements": requirements,
        "salary_range": None,
        "source": source_name,
        "source_url": offer_url,
        "posted_date": posted_date,
        "valid_through": None,
        "is_active": True,
    }


async def _collect_cvparser(
    client: httpx.AsyncClient, source: Dict[str, object], existing_ids: set, existing_urls: set, limit: int
) -> List[Dict[str, object]]:
    """Mode 'cvparser_api' : plateforme CVParser (Tectra, etc.). Les offres sont
    servies par une API JSON `{api_base}/annonces?p=N` (pagination 0-indexée).
    L'URL publique (humaine, pour postuler) est `{detail_base}/{id}`."""
    name = str(source["name"])
    api_base = str(source["api_base"]).rstrip("/")
    detail_base = str(source["detail_base"]).rstrip("/")
    company = str(source.get("company") or name)

    new_offers: List[Dict[str, object]] = []
    for page in range(0, max(1, listing_pages())):
        text = await _fetch(client, f"{api_base}/annonces?p={page}")
        await asyncio.sleep(0.5)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Aggregator[%s]: JSON invalide (page %d)", name, page)
            continue
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not rows:
            break  # plus d'offres -> on arrête la pagination
        logger.info("Aggregator[%s]: %d offres dans la page %d", name, len(rows), page)
        for o in rows:
            if len(new_offers) >= limit:
                break
            if not isinstance(o, dict):
                continue
            oid = str(o.get("id") or "").strip()
            if not oid:
                continue
            offer_url = f"{detail_base}/{oid}"
            if oid in existing_ids or offer_url in existing_urls:
                continue
            offer = _map_cvparser_offer(o, offer_url, name, company)
            if offer:
                new_offers.append(offer)
                existing_urls.add(offer_url)  # évite les doublons inter-pages
                existing_ids.add(oid)
        if len(new_offers) >= limit:
            break
    return new_offers


async def collect_source(
    client: httpx.AsyncClient, source: Dict[str, object], existing_ids: set, existing_urls: set, limit: int
) -> List[Dict[str, object]]:
    """Renvoie les offres NOUVELLES (non déjà en base) d'une source, mappées."""
    name = str(source["name"])
    id_re: Pattern = source["id_re"]  # type: ignore[assignment]

    if source.get("mode") == "cvparser_api":
        return await _collect_cvparser(client, source, existing_ids, existing_urls, limit)

    if source.get("mode") == "listing_jsonld":
        return await _collect_listing_jsonld(client, source, existing_ids, existing_urls, limit)

    urls = await _collect_listing_urls(client, source, listing_pages())
    logger.info("Aggregator[%s]: %d offres listées", name, len(urls))

    new_offers: List[Dict[str, object]] = []
    for url in urls:
        if len(new_offers) >= limit:
            break
        # Dédup AVANT téléchargement: par identifiant externe quand disponible, et
        # toujours par URL complète (certaines URLs n'ont pas d'ID extractible).
        if url in existing_urls:
            continue
        ext_id = _extract_external_id(url, id_re)
        if ext_id and ext_id in existing_ids:
            continue  # déjà en base -> on ne re-télécharge même pas la page
        html = await _fetch(client, url)
        await asyncio.sleep(0.7)  # politesse: délai entre pages détail
        if not html:
            continue
        posting = _parse_job_posting(html)
        if not posting:
            logger.debug("Aggregator[%s]: pas de JobPosting sur %s", name, url)
            continue
        offer = _map_to_offer(posting, url, name)
        if offer:
            new_offers.append(offer)
    return new_offers


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
async def _load_existing(service: Job_offersService, source: Dict[str, object]):
    """Retourne (ids externes, urls complètes) déjà présents pour une source."""
    name = str(source["name"])
    id_re: Pattern = source["id_re"]  # type: ignore[assignment]
    ids: set = set()
    urls: set = set()
    # limit élevé: la dédup doit couvrir TOUTES les offres importées de cette source.
    offers = await service.list_by_field("source", name, skip=0, limit=100000)
    for o in offers or []:
        url = o.source_url or ""
        if url:
            urls.add(url)
        ext = _extract_external_id(url, id_re)
        if ext:
            ids.add(ext)
    return ids, urls


async def expire_stale_offers() -> int:
    """Désactive (is_active=False) les offres dont la date de validité est passée."""
    if not db_manager.async_session_maker:
        return 0
    from sqlalchemy import update

    from models.job_offers import Job_offers

    today = datetime.now().strftime("%Y-%m-%d")
    async with db_manager.async_session_maker() as session:
        result = await session.execute(
            update(Job_offers)
            .where(
                Job_offers.valid_through.isnot(None),
                Job_offers.valid_through != "",
                Job_offers.valid_through < today,
                Job_offers.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await session.commit()
        n = result.rowcount or 0
        if n:
            logger.info("Aggregator: %d offre(s) expirée(s) désactivée(s)", n)
        return n


async def run_aggregation() -> int:
    """Exécute une passe d'agrégation sur toutes les sources. Renvoie le nb inséré."""
    if not aggregator_enabled():
        logger.info("Aggregator désactivé (AGGREGATOR_ENABLED=false)")
        return 0
    if not db_manager.async_session_maker:
        logger.warning("Aggregator: base non initialisée, passe ignorée")
        return 0

    # Toujours expirer les offres périmées, même si aucune nouvelle n'est insérée.
    await expire_stale_offers()

    only = _enabled_source_names()
    sources = [s for s in SOURCES if only is None or str(s["name"]).lower() in only]

    inserted = 0
    started = datetime.now()
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True) as client:
            async with db_manager.async_session_maker() as session:
                service = Job_offersService(session)

                for source in sources:
                    name = str(source["name"])
                    try:
                        existing_ids, existing_urls = await _load_existing(service, source)
                        logger.info("Aggregator[%s]: %d offres déjà connues", name, len(existing_urls))
                        offers = await collect_source(client, source, existing_ids, existing_urls, max_per_run())
                    except Exception as exc:  # pragma: no cover - défensif
                        logger.error("Aggregator[%s]: source en échec: %s", name, exc)
                        continue

                    src_inserted = 0
                    for offer in offers:
                        try:
                            created = await service.create(offer)
                            if created:
                                src_inserted += 1
                        except Exception as exc:  # pragma: no cover - défensif
                            logger.error("Aggregator[%s]: insertion échouée (%s): %s", name, offer.get("title"), exc)
                    inserted += src_inserted
                    logger.info("Aggregator[%s]: %d nouvelle(s) offre(s)", name, src_inserted)
    except Exception as exc:  # pragma: no cover - défensif
        logger.error("Aggregator: passe interrompue: %s", exc, exc_info=True)

    logger.info(
        "Aggregator: %d nouvelle(s) offre(s) insérée(s) au total en %.1fs",
        inserted,
        (datetime.now() - started).total_seconds(),
    )
    return inserted
