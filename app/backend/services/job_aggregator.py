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
from html import unescape as _html_unescape
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
    # Sites jumeaux du même réseau « Emploi.XX » (structure identique à Emploi.ci/.sn)
    # → le parser JSON-LD par défaut fonctionne tel quel. Élargit à l'Afrique de l'Ouest.
    # Résilient : un domaine/slug introuvable renvoie simplement 0 offre (log warning).
    {
        "name": "Emploi.bf",
        "base": "https://www.emploi.bf",
        "listing_path": "/recherche-jobs-burkina-faso",
        "offer_re": re.compile(r"/offre-emploi-burkina-faso/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Emploi.ml",
        "base": "https://www.emploi.ml",
        "listing_path": "/recherche-jobs-mali",
        "offer_re": re.compile(r"/offre-emploi-mali/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Emploi.tg",
        "base": "https://www.emploi.tg",
        "listing_path": "/recherche-jobs-togo",
        "offer_re": re.compile(r"/offre-emploi-togo/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Emploi.bj",
        "base": "https://www.emploi.bj",
        "listing_path": "/recherche-jobs-benin",
        "offer_re": re.compile(r"/offre-emploi-benin/[a-z0-9-]+", re.I),
        "id_re": re.compile(r"-(\d+)(?:[/?#]|$)"),
        "paginate": True,
    },
    {
        "name": "Emploi.gn",
        "base": "https://www.emploi.gn",
        "listing_path": "/recherche-jobs-guinee",
        "offer_re": re.compile(r"/offre-emploi-guinee/[a-z0-9-]+", re.I),
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
        # AfriqueEmplois (opérateur « E-Faso ») : la page liste n'embarque plus de
        # JobPosting (oct. 2026) → crawl des pages détail, dont le JSON-LD porte le
        # VRAI employeur. Les liens de la liste sont absolus ; pagination ?page=N.
        "name": "AfriqueEmplois",
        "base": "https://afriqueemplois.com",
        "listing_path": "/ci",
        "offer_re": re.compile(r"https://afriqueemplois\.com/ci/post/\d+", re.I),
        "id_re": re.compile(r"/post/(\d+)"),
        "paginate": True,
    },
    {
        # Educarriere.ci : 1er site emploi ivoirien. Board server-rendered (pas de
        # JSON-LD) sur le sous-domaine emploi.educarriere.ci ; parser HTML dédié.
        # `/emploi/page/all` liste ~28 offres récentes (liens /offre-{id}-{slug}.html).
        "name": "Educarriere",
        "base": "https://emploi.educarriere.ci",
        "listing_path": "/emploi/page/all",
        "mode": "educarriere_html",
        "offer_re": re.compile(r"/offre-\d+-[a-z0-9-]+\.html", re.I),
        "id_re": re.compile(r"/offre-(\d+)-"),
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


_BLOCK_END_RE = re.compile(r"</(?:p|div|h[1-6]|li|ul|ol|tr)\s*>|<br\s*/?>", re.I)
_LI_START_RE = re.compile(r"<li[^>]*>", re.I)


def _html_to_text(text: str) -> str:
    """HTML → texte lisible en gardant paragraphes et puces (affiché en pre-line)."""
    t = _LI_START_RE.sub("\n• ", text or "")
    t = _BLOCK_END_RE.sub("\n", t)
    t = _html_unescape(_HTML_TAG_RE.sub(" ", t))
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in t.split("\n")]
    merged: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if merged and merged[-1] == "•":  # puce vide (listes imbriquées) → fusion
            merged[-1] = "• " + ln.lstrip("• ")
        else:
            merged.append(ln)
    out = "\n".join(merged)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _strip_html(text: str) -> str:
    # Retire les balises PUIS décode les entités HTML (&rsquo; &#9679; &amp; …).
    stripped = _HTML_TAG_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", _html_unescape(stripped)).strip()


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
# Secteurs canoniques (= métier du poste) et mots-clés. Chaque mot-clé est cherché
# en DÉBUT de mot (« audit » trouve « auditeur », pas « inaudible ») ; les mots-clés
# courts (≤ 3 lettres) ou finis par une espace doivent être un mot ENTIER ; FR + EN car
# certaines sources (Tectra, LinkedIn) publient en anglais.
_SECTOR_RULES = [
    ("Fintech", ["fintech", "paiement mobile", "mobile money", "monétique"]),
    ("Télécommunications", ["télécom", "telecom", "fibre optique", "gsm", "radio fréquence", "rf engineer"]),
    ("Informatique / Tech", [
        "développeu", "developpeu", "developer", "logiciel", "software", "informatique", "it ",
        "data", "devops", "programmation", "programmeu", "réseau", "network", "cybersécurité", "cybersecurity",
        "web", "full stack", "fullstack", "frontend", "front-end", "backend", "back-end",
        "sap", "erp", "cloud", "système d'information", "système", "systems", "helpdesk",
        "support it", "qa ", "quality assurance", "ui", "ux", "machine learning", "ia ", "ai ",
        "intelligence artificielle", "digital", "numérique", "python", "java", ".net", "php",
        "blockchain", "crypto", "rust",
    ]),
    ("Comptabilité / Audit", [
        "comptab", "audit", "fiscal", "contrôle de gestion", "contrôleur de gestion", "trésor",
        "accountant", "accounting", "bookkeep", "controller", "payroll accountant",
    ]),
    ("Finance / Banque", [
        "banque", "bancaire", "finance", "financ", "crédit", "microfinance", "assurance",
        "actuair", "bank", "insurance", "investment", "chargé d'affaires", "conseiller clientèle",
        "souscripteur", "risk", "risque", "compliance", "conformité", "recouvrement",
    ]),
    ("Marketing / Communication", [
        "marketing", "communication", "community manager", "seo", "publicité", "média",
        "contenu", "content", "brand", "marque", "graphi", "motion", "designer", "rédact",
        "journalis", "éditorial", "relations presse", "social media", "vidéaste", "cadreur",
        "monteur vidéo", "photograph", "événementiel", "events",
    ]),
    ("Logistique / Transport", [
        "logisti", "supply chain", "transport", "approvisionnement", "fret", "douane", "transit",
        "import-export", "magasinier", "chauffeur", "driver", "cargo", "achat", "acheteur",
        "procurement", "flotte", "entrepôt", "warehouse", "shipping", "maritime", "portuaire",
        "conducteur routier", "conducteurs routiers", "routier", "livreu", "coursier",
    ]),
    ("BTP / Construction", [
        "btp", "construction", "génie civil", "chantier", "bâtiment", "immobilier", "architect",
        "travaux", "topograph", "conducteur de travaux", "civil engineer", "maçon", "plombier",
    ]),
    ("Commerce / Vente", [
        "commercia", "vente", "vendeu", "business development", "business developer",
        "négociat", "télévente", "sales", "caissi", "account manager", "key account",
        "merchandis", "bizdev", "téléconseiller", "call center", "centre d'appels", "customer service",
        "service client", "relation client", "agent commercial", "boutique", "retail",
    ]),
    ("Ressources Humaines", [
        "ressources humaines", "rh ", "recrutement", "recruteu", "recruiter", "paie",
        "talent", "human resources", "hr ", "people", "formation du personnel",
        "administration du personnel", "gestion du personnel",
    ]),
    ("Santé", [
        "santé", "médic", "infirmi", "médecin", "pharmac", "hôpital", "soignant", "sage-femme",
        "laborantin", "laboratoire", "laboratory", "nurse", "medical", "health", "clinique",
        "biolog", "opticien", "dentist", "kiné",
    ]),
    ("Éducation / Formation", [
        "enseign", "formation", "pédagog", "éducat", "professeur", "formateur", "teacher",
        "instituteur", "école", "tutor", "trainer", "e-learning", "coach",
    ]),
    ("Juridique", ["juridique", "avocat", "juriste", "notaire", "legal", "lawyer", "droit des",
                   "propriété intellectuelle", "intellectual property"]),
    ("Agroalimentaire / Agriculture", [
        "agro", "agricole", "agriculture", "élevage", "agronom", "farm", "cacao", "hévéa",
        "palmier", "plantation", "pêche", "vétérinaire",
    ]),
    ("Énergie / Mines", [
        "énergie", "energy", "électricité", "pétrol", "petroleum", "gaz", "oil", "mine",
        "minier", "mining", "solaire", "solar", "électrici", "hse", "qhse",
    ]),
    ("Industrie", [
        "industri", "production", "usine", "manufactur", "maintenance", "mécani", "électromécani",
        "ingénierie", "qualité", "chimie", "métallurgie", "textile", "plasturg", "technicien",
        "operator", "opérateur",
    ]),
    ("Hôtellerie / Tourisme", [
        "hôtel", "hotel", "restaura", "tourisme", "cuisin", "chef cuisinier", "serveu",
        "barman", "réception", "receptionist", "housekeep", "voyage", "travel",
    ]),
    ("Administration / Secrétariat", [
        "assistant", "assistante", "secrétai", "secretary", "administrati", "admin ",
        "office manager", "accueil", "archiv", "standardiste", "gestionnaire de bureau",
        "saisie", "services généraux", "moyens généraux",
    ]),
    ("Humanitaire / ONG", [
        "humanitaire", "ong", "ngo", "unicef", "pnud", "undp", "unfpa", "programme alimentaire",
        "msf", "médecins sans frontières", "croix-rouge", "suivi-évaluation", "suivi, évaluation",
        "monitoring and evaluation", "développement communautaire",
    ]),
    ("Sécurité / Gardiennage", ["sécurité privée", "gardien", "vigile", "agent de sécurité", "security guard"]),
    ("Direction / Management", [
        "directeur", "directrice", "director", "country manager", "general manager",
        "chef de projet", "project manager", "manager", "responsable", "coordinat", "gérant",
    ]),
]

# Compilé une fois : (libellé, [motifs « début de mot »]).
_SECTOR_PATTERNS = [
    (label, [re.compile(r"(?<![\w])" + re.escape(k.strip())
                        + (r"(?![\w])" if k.endswith(" ") or len(k.strip()) <= 3 else ""), re.I)
             for k in keys])
    for label, keys in _SECTOR_RULES
]
# Secteurs « fonction transverse » : ne l'emportent que faute de mieux.
_WEAK_SECTORS = {"Direction / Management", "Administration / Secrétariat"}


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


_BIZDEV_RE = re.compile(r"business\s+develop\w*", re.I)


def _sector_scores(text: str, weight: float, scores: Dict[str, float]) -> None:
    # « Business Developer » est un poste commercial, pas de développeur.
    text = _BIZDEV_RE.sub("bizdev", text)
    for label, patterns in _SECTOR_PATTERNS:
        hits = sum(1 for pat in patterns if pat.search(text))
        if hits:
            scores[label] = scores.get(label, 0.0) + weight * hits


def _classify_sector(text: str) -> Optional[str]:
    scores: Dict[str, float] = {}
    _sector_scores(text or "", 1.0, scores)
    return _best_sector(scores)


def _best_sector(scores: Dict[str, float]) -> Optional[str]:
    if not scores:
        return None
    # À score égal ou proche, un métier précis bat une fonction transverse (manager, assistant).
    ranked = sorted(scores.items(), key=lambda kv: (kv[1] - (0.5 if kv[0] in _WEAK_SECTORS else 0)), reverse=True)
    return ranked[0][0]


def normalize_sector(raw: Optional[str], title: str = "", description: str = "") -> Optional[str]:
    """Secteur canonique = métier du POSTE.

    Score pondéré : le titre domine (×4), le libellé de la source aide (×2), la
    description ne sert qu'en appoint (×0.5, plafonné) — elle cite souvent des mots
    sans rapport (« outils informatiques », « assurance maladie »). Un libellé de
    source inconnu n'est plus conservé tel quel : tout tombe dans la liste canonique,
    sinon « Autres ».
    """
    scores: Dict[str, float] = {}
    _sector_scores(title or "", 4.0, scores)
    _sector_scores(raw or "", 2.0, scores)
    desc_scores: Dict[str, float] = {}
    _sector_scores((description or "")[:1500], 0.5, desc_scores)
    for label, val in desc_scores.items():
        scores[label] = scores.get(label, 0.0) + min(val, 1.5)
    best = _best_sector(scores)
    if best:
        return best
    return "Autres" if (raw or title) else None


async def _fetch(
    client: httpx.AsyncClient, url: str, retries: int = 2, headers: Optional[dict] = None
) -> Optional[str]:
    """GET avec reprises (certains sites comme Novojob sont intermittents).

    `headers` (optionnel) surcharge les en-têtes par requête — utile pour une source
    qui exige un User-Agent de navigateur (ex. Educarriere)."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, headers=headers) if headers else await client.get(url)
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


def _sane_posted_date(raw: Optional[str]) -> Optional[str]:
    """Assainit une date de publication issue d'une source (souvent peu fiable).

    Certaines sources émettent des `datePosted` aberrantes : date epoch-ish
    (ex. '2020-01-01'), date dans le futur, ou format inattendu. On ne garde la
    date que si elle est plausible : parseable, pas dans le futur, et pas plus
    vieille d'un an (ces boards ne listent que des offres récentes). Sinon on
    renvoie None — l'offre retombe alors sur `created_at` côté affichage.
    Retour : 'YYYY-MM-DD' ou None.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    head = raw.strip()[:10]
    try:
        d = datetime.strptime(head, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now().date()
    if d > today:
        return None  # date future → invalide
    if (today - d).days > 365:
        return None  # trop vieille → vraisemblablement bidon
    return head


# Opérateurs de sites d'annonces déclarés à tort comme `hiringOrganization`
# (le vrai employeur est alors dans la description ou le titre).
_OPERATOR_COMPANIES = {"e-faso"}
CONFIDENTIAL_EMPLOYER = "Employeur confidentiel"

# « Entreprise : LEADWAY ASSURANCE » en tête de description (HTML ou texte aplati,
# où l'étiquette suivante est collée : « …ASSURANCELieu : Abidjan »).
_DESC_EMPLOYER_RE = re.compile(
    r"Entreprise\s*:\s*(?:</strong>)?\s*(.+?)(?=<|Lieu\s*:|Type de contrat\s*:|Date limite\s*:|\n|$)",
    re.I,
)
# « Wave recrute un… », « Les Écoles Maarif recrutent… »
_TITLE_EMPLOYER_RE = re.compile(r"^(.+?)\s+recrute(?:nt)?\b", re.I)
_LEADING_ARTICLE_RE = re.compile(r"^(?:la|le|les)\s+|^l['’]\s*", re.I)


_CONFIDENTIAL_NAMES = {"confidential company", "confidential", "confidentiel", "entreprise confidentielle"}
# Certaines sources mettent un niveau d'études dans `industry` (« Niveau BAC », « < BEPC »).
_EDUCATION_LEVEL_RE = re.compile(r"\b(?:bac|bepc|cepe|niveau|licence|master|doctorat)\b", re.I)


def normalize_company(name: str) -> str:
    return CONFIDENTIAL_EMPLOYER if name.strip().lower() in _CONFIDENTIAL_NAMES else name.strip()


def is_operator_company(company: Optional[str]) -> bool:
    return (company or "").strip().lower() in _OPERATOR_COMPANIES


def infer_employer(title: str, description: Optional[str]) -> Optional[str]:
    """Vrai employeur d'une annonce d'opérateur : description, puis titre."""
    m = _DESC_EMPLOYER_RE.search(description or "")
    if m:
        name = _html_unescape(m.group(1)).strip(" .:-–")
        if 2 <= len(name) <= 80:
            return normalize_company(name)
    m = _TITLE_EMPLOYER_RE.match((title or "").strip())
    if m:
        name = _LEADING_ARTICLE_RE.sub("", m.group(1)).strip(" .:-–")
        if 2 <= len(name) <= 80:
            return name[0].upper() + name[1:]
    return None


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

    raw_description = str(posting.get("description", ""))
    description = _html_to_text(raw_description)[:4000] or None
    if not company or is_operator_company(company):
        company = infer_employer(title, raw_description) or (CONFIDENTIAL_EMPLOYER if company else "")
    company = normalize_company(company) if company else company
    requirements = _strip_html(str(posting.get("qualifications") or posting.get("experienceRequirements") or "")) or None

    industry = posting.get("industry")
    raw_sector = industry if isinstance(industry, str) and not _EDUCATION_LEVEL_RE.search(industry) else None
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

    dp = posting.get("datePosted")
    posted_date = _sane_posted_date(dp if isinstance(dp, str) else None)

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

    dt = o.get("date")
    posted_date = _sane_posted_date(dt if isinstance(dt, str) else None)

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


# --------------------------------------------------------------------------- #
# Educarriere.ci : HTML rendu serveur, SANS JSON-LD. Les pages détail exposent les
# champs en `<li class="list-group-item"><strong>Label:</strong> valeur</li>` et la
# description dans `<meta property="og:description">`. Mode dédié `educarriere_html`.
# --------------------------------------------------------------------------- #
_EDUCARRIERE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _educ_field(html: str, label: str) -> Optional[str]:
    m = re.search(
        r"<strong>\s*" + re.escape(label) + r"[^<]*</strong>\s*(?:<span[^>]*>)?\s*([^<]+)",
        html, re.I,
    )
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def _educ_date(raw: Optional[str]) -> Optional[str]:
    """'06/07/2026' -> '2026-07-06'."""
    if not raw:
        return None
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", raw.strip())
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _map_educarriere(html: str, offer_url: str, source_name: str) -> Optional[Dict[str, object]]:
    title = None
    h = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S | re.I)
    if h:
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h.group(1))).strip()
    if not title:
        t = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        if t:
            title = re.sub(r"\s*-\s*Offres d'emploi.*$", "", re.sub(r"<[^>]+>", "", t.group(1))).strip()
    if not title:
        return None
    title = _html_unescape(title)

    metier = _educ_field(html, "Métier")
    desc = None
    md = re.search(
        r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\'](.*?)["\']\s*/?>',
        html, re.I | re.S,
    )
    if md:
        desc = re.sub(r"^Description (?:du|de) poste\s*:?\s*", "", _strip_html(md.group(1)).strip(), flags=re.I)
        desc = desc[:4000] or None

    reqs = []
    niveau = _educ_field(html, "Niveau")
    exp = _educ_field(html, "Expérience")
    if niveau:
        reqs.append(f"Niveau : {niveau}")
    if exp:
        reqs.append(f"Expérience : {exp}")

    return {
        "title": title[:255],
        # L'employeur réel est masqué derrière un login sur Educarriere.
        "company": "Recruteur via Educarriere"[:255],
        "location": normalize_location(_educ_field(html, "Lieu")),
        "contract_type": normalize_contract_type(title),
        "sector": normalize_sector(metier, title, desc or ""),
        "description": desc,
        "requirements": " · ".join(reqs) or None,
        "salary_range": None,
        "source": source_name,
        "source_url": offer_url,
        "posted_date": _sane_posted_date(_educ_date(_educ_field(html, "Date de publication"))),
        "valid_through": _educ_date(_educ_field(html, "Date limite")),
        "is_active": True,
    }


async def _collect_educarriere(
    client: httpx.AsyncClient, source: Dict[str, object], existing_ids: set, existing_urls: set, limit: int
) -> List[Dict[str, object]]:
    """Mode 'educarriere_html' : liste server-rendered → crawl des pages détail (HTML)."""
    name = str(source["name"])
    base = str(source["base"]).rstrip("/")
    offer_re: Pattern = source["offer_re"]  # type: ignore[assignment]
    id_re: Pattern = source["id_re"]  # type: ignore[assignment]
    headers = {"User-Agent": _EDUCARRIERE_UA}

    list_html = await _fetch(client, base + str(source["listing_path"]), headers=headers)
    if not list_html:
        return []

    seen, urls = set(), []
    for m in offer_re.finditer(list_html):
        path = m.group(0)
        url = path if path.startswith("http") else base + path
        if url not in seen:
            seen.add(url)
            urls.append(url)
    logger.info("Aggregator[%s]: %d offres listées", name, len(urls))

    new_offers: List[Dict[str, object]] = []
    for url in urls:
        if len(new_offers) >= limit:
            break
        if url in existing_urls:
            continue
        ext_id = _extract_external_id(url, id_re)
        if ext_id and ext_id in existing_ids:
            continue
        html = await _fetch(client, url, headers=headers)
        await asyncio.sleep(0.7)
        if not html:
            continue
        offer = _map_educarriere(html, url, name)
        if offer:
            new_offers.append(offer)
            existing_urls.add(url)
            if ext_id:
                existing_ids.add(ext_id)
    return new_offers


async def collect_source(
    client: httpx.AsyncClient, source: Dict[str, object], existing_ids: set, existing_urls: set, limit: int
) -> List[Dict[str, object]]:
    """Renvoie les offres NOUVELLES (non déjà en base) d'une source, mappées."""
    name = str(source["name"])
    id_re: Pattern = source["id_re"]  # type: ignore[assignment]

    if source.get("mode") == "cvparser_api":
        return await _collect_cvparser(client, source, existing_ids, existing_urls, limit)

    if source.get("mode") == "educarriere_html":
        return await _collect_educarriere(client, source, existing_ids, existing_urls, limit)

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


async def fix_operator_companies() -> int:
    """Corrige les offres déjà en base attribuées à un opérateur (ex. « E-Faso »).

    Idempotent : une fois corrigée, l'offre ne correspond plus au filtre.
    """
    if not db_manager.async_session_maker:
        return 0
    from sqlalchemy import func, select

    from models.job_offers import Job_offers

    fixed = 0
    async with db_manager.async_session_maker() as session:
        rows = (await session.execute(
            select(Job_offers).where(
                func.lower(Job_offers.company).in_(_OPERATOR_COMPANIES | _CONFIDENTIAL_NAMES)
            )
        )).scalars().all()
        for job in rows:
            if is_operator_company(job.company):
                job.company = (infer_employer(job.title, job.description) or CONFIDENTIAL_EMPLOYER)[:255]
            else:
                job.company = CONFIDENTIAL_EMPLOYER
            fixed += 1
        if fixed:
            await session.commit()
            logger.info("Aggregator: employeur corrigé sur %d offre(s) d'opérateur", fixed)
    return fixed


# Secteurs canoniques AVANT la refonte du classement (oct. 2026) : en base, on ne
# sait plus s'ils venaient de la source ou d'une déduction (souvent fausse) → ignorés
# au reclassement ; les autres valeurs sont des libellés bruts de source, conservés
# comme indice.
_LEGACY_CANONICAL_SECTORS = {
    "Fintech", "Télécommunications", "Informatique / Tech", "Comptabilité / Audit",
    "Finance / Banque", "Marketing / Communication", "Logistique / Transport",
    "BTP / Construction", "Commerce / Vente", "Ressources Humaines", "Santé",
    "Éducation / Formation", "Juridique", "Agroalimentaire / Agriculture", "Industrie",
    "Hôtellerie / Tourisme",
}
_sectors_reclassified = False


async def reclassify_sectors() -> int:
    """Reclasse une fois par processus les offres AGRÉGÉES avec le classement actuel.

    Les offres de recruteurs (secteur choisi par eux) ne sont jamais touchées.
    """
    global _sectors_reclassified
    if _sectors_reclassified or not db_manager.async_session_maker:
        return 0
    from sqlalchemy import select

    from models.job_offers import Job_offers
    from models.job_postings import Job_postings

    changed = 0
    async with db_manager.async_session_maker() as session:
        recruiter_ids = set((await session.execute(select(Job_postings.job_id))).scalars().all())
        rows = (await session.execute(select(Job_offers).where(Job_offers.source.isnot(None)))).scalars().all()
        for job in rows:
            if job.id in recruiter_ids:
                continue
            raw = job.sector if job.sector and job.sector not in _LEGACY_CANONICAL_SECTORS else None
            new = normalize_sector(raw, job.title or "", job.description or "")
            if new == "Autres" and job.sector in _LEGACY_CANONICAL_SECTORS:
                new = job.sector  # rien de mieux : on garde l'ancien
            if new and new != job.sector:
                job.sector = new
                changed += 1
        if changed:
            await session.commit()
    _sectors_reclassified = True
    logger.info("Aggregator: secteur reclassé sur %d offre(s)", changed)
    return changed


# Bloc de contenu des pages détail AfriqueEmplois (description complète).
_AE_PROSE_RE = re.compile(r'<div class="prose[^"]*"[^>]*>', re.I)
_DIV_TAG_RE = re.compile(r"<(/?)div\b", re.I)
_enrich_attempted: set = set()


def _extract_prose(page: str) -> Optional[str]:
    m = _AE_PROSE_RE.search(page or "")
    if not m:
        return None
    depth, pos = 1, m.end()
    for tag in _DIV_TAG_RE.finditer(page, pos):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return page[m.end():tag.start()]
    return None


async def enrich_short_descriptions(client: httpx.AsyncClient, limit: int = 40) -> int:
    """Complète les descriptions tronquées (~200 car.) d'AfriqueEmplois depuis la page
    détail, par lots (politesse). Recalcule employeur et secteur avec le texte complet."""
    if not db_manager.async_session_maker:
        return 0
    from sqlalchemy import func, select

    from models.job_offers import Job_offers

    enriched = 0
    async with db_manager.async_session_maker() as session:
        rows = (await session.execute(
            select(Job_offers)
            .where(Job_offers.source == "AfriqueEmplois", func.length(Job_offers.description) < 400,
                   Job_offers.source_url.isnot(None))
            .order_by(Job_offers.id.desc())
        )).scalars().all()
        rows = [r for r in rows if r.id not in _enrich_attempted][:limit]
        for job in rows:
            _enrich_attempted.add(job.id)
            page = await _fetch(client, job.source_url)
            await asyncio.sleep(0.7)
            body = _extract_prose(page or "")
            text = _html_to_text(body or "")
            if len(text) <= len(job.description or ""):
                continue
            job.description = text[:4000]
            if job.company == CONFIDENTIAL_EMPLOYER:
                job.company = (infer_employer(job.title, body) or CONFIDENTIAL_EMPLOYER)[:255]
            job.sector = normalize_sector(None, job.title or "", job.description)
            enriched += 1
        if enriched:
            await session.commit()
    if rows:
        logger.info("Aggregator: %d/%d description(s) complétée(s)", enriched, len(rows))
    return enriched


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
    await fix_operator_companies()
    await reclassify_sectors()

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

            if any(str(src["name"]) == "AfriqueEmplois" for src in sources):
                try:
                    await enrich_short_descriptions(client)
                except Exception as exc:  # pragma: no cover - défensif
                    logger.error("Aggregator: enrichissement des descriptions en échec: %s", exc)
    except Exception as exc:  # pragma: no cover - défensif
        logger.error("Aggregator: passe interrompue: %s", exc, exc_info=True)

    logger.info(
        "Aggregator: %d nouvelle(s) offre(s) insérée(s) au total en %.1fs",
        inserted,
        (datetime.now() - started).total_seconds(),
    )
    return inserted
