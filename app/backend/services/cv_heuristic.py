"""
Local, key-free heuristic engine for CV analysis and job-compatibility scoring.

Used as the default when no external AI provider is configured
(APP_AI_BASE_URL / APP_AI_KEY empty), and as a fallback when an AI call fails.

Everything here is deterministic and offline:
- PDF text is extracted with PyMuPDF (fitz)
- Profile fields are parsed with regex + curated keyword dictionaries
- Compatibility is scored by skill/sector/location/experience matching
"""

import base64
import binascii
import logging
import re
from typing import Any, Dict, List, Optional

import fitz

logger = logging.getLogger(__name__)

# --- Curated dictionaries (tech + general, West-Africa job market oriented) ---
SKILL_KEYWORDS = [
    # Tech
    "python", "java", "javascript", "typescript", "php", "c++", "c#", "go", "rust",
    "ruby", "kotlin", "swift", "sql", "nosql", "postgresql", "mysql", "mongodb",
    "react", "vue", "angular", "node", "node.js", "django", "flask", "fastapi",
    "spring", "laravel", "symfony", "html", "css", "tailwind", "bootstrap",
    "docker", "kubernetes", "aws", "azure", "gcp", "git", "ci/cd", "linux",
    "machine learning", "deep learning", "data science", "data analysis", "pandas",
    "numpy", "tensorflow", "pytorch", "power bi", "tableau", "excel", "vba",
    "api", "api rest", "rest", "graphql", "microservices", "devops", "agile", "scrum",
    "cybersécurité", "sécurité", "réseau", "réseaux", "administration système",
    # Finance / Fintech
    "comptabilité", "finance", "audit", "fiscalité", "contrôle de gestion",
    "paiement mobile", "mobile money", "banque", "crédit", "microfinance",
    # Marketing / Digital
    "marketing", "marketing digital", "seo", "sea", "community management",
    "réseaux sociaux", "rédaction web", "content", "branding", "communication",
    "google analytics", "publicité", "e-commerce",
    # Logistique / Supply
    "logistique", "supply chain", "transport", "approvisionnement", "achats",
    "gestion de stock", "import-export", "douane",
    # RH / Admin / Commercial
    "ressources humaines", "recrutement", "paie", "gestion de projet",
    "vente", "commercial", "négociation", "relation client", "service client",
    "management", "leadership", "organisation", "rigueur", "autonomie",
    # Santé / Education / BTP
    "santé", "infirmier", "médecine", "pédagogie", "formation", "enseignement",
    "btp", "génie civil", "architecture", "électricité", "mécanique",
]

SECTOR_KEYWORDS = {
    "Informatique / Tech": ["développeur", "developpeur", "logiciel", "software", "informatique",
                            "data", "devops", "web", "mobile", "it", "tech"],
    "Fintech": ["fintech", "paiement", "mobile money", "banque", "finance", "crédit", "microfinance"],
    "Marketing Digital": ["marketing", "community", "seo", "digital", "communication", "publicité"],
    "Logistique": ["logistique", "supply chain", "transport", "approvisionnement", "douane"],
    "Comptabilité / Finance": ["comptable", "comptabilité", "audit", "fiscalité", "contrôle de gestion"],
    "Ressources Humaines": ["ressources humaines", "recrutement", "rh", "paie"],
    "Commercial / Vente": ["commercial", "vente", "business", "négociation"],
    "Santé": ["infirmier", "médecin", "santé", "soignant", "pharmacie"],
    "Éducation": ["enseignant", "professeur", "formateur", "pédagogie", "éducation"],
    "BTP / Génie civil": ["btp", "génie civil", "chantier", "architecte", "électricien"],
}

EDUCATION_LEVELS = [
    (r"\b(doctorat|phd|ph\.d)\b", "Doctorat"),
    (r"\b(master|bac\s*\+\s*5|maîtrise|ingénieur)\b", "Master / Bac+5"),
    (r"\b(licence|bachelor|bac\s*\+\s*3)\b", "Licence / Bac+3"),
    (r"\b(bts|dut|bac\s*\+\s*2|deug)\b", "BTS / DUT / Bac+2"),
    (r"\b(baccalauréat|baccalaureat|\bbac\b)\b", "Baccalauréat"),
]

# West-African (and common French-speaking) locations
LOCATIONS = [
    "abidjan", "yamoussoukro", "bouaké", "dakar", "thiès", "lomé", "cotonou",
    "porto-novo", "ouagadougou", "bobo-dioulasso", "bamako", "niamey", "conakry",
    "accra", "lagos", "douala", "yaoundé", "libreville", "kinshasa", "côte d'ivoire",
    "sénégal", "togo", "bénin", "burkina faso", "mali", "niger", "guinée", "ghana",
    "nigeria", "cameroun", "gabon", "paris", "france", "maroc", "tunisie",
]

JOB_TITLE_HINTS = [
    "développeur", "developpeur", "ingénieur", "comptable", "commercial",
    "assistant", "responsable", "chef de projet", "manager", "directeur",
    "technicien", "consultant", "analyste", "designer", "community manager",
    "chargé", "gestionnaire", "agent", "coordinateur", "auditeur",
]

FRENCH_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "en", "à",
    "au", "aux", "pour", "par", "sur", "dans", "avec", "sans", "ce", "ces",
    "se", "sa", "son", "ses", "qui", "que", "quoi", "dont", "est", "sont",
    "the", "and", "or", "of", "to", "in", "a", "an", "for", "with", "on",
    "ans", "an", "année", "années", "experience", "expérience", "ainsi", "etc",
}


def decode_pdf_text(pdf_base64: str) -> str:
    """Decode a base64 (optionally data-URI) PDF and return its extracted text."""
    payload = pdf_base64.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    try:
        raw = base64.b64decode(payload)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid base64 PDF payload") from exc

    text_parts: List[str] = []
    with fitz.open(stream=raw, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _tokens(text: Optional[str]) -> set:
    if not text:
        return set()
    raw = re.findall(r"[a-zàâäéèêëïîôöùûüç0-9+#.]{2,}", text.lower())
    return {t for t in raw if t not in FRENCH_STOPWORDS}


def _skill_present(skill: str, low_text: str) -> bool:
    """Whether a skill occurs in the text. Word-boundary match for plain alphabetic
    skills (avoids 'go' in 'Django', 'paie' in 'paiement'); substring match for
    skills containing special chars (c++, c#, node.js, api rest, ci/cd)."""
    if re.fullmatch(r"[a-zàâäéèêëïîôöùûüç]+", skill):
        return re.search(rf"\b{re.escape(skill)}\b", low_text) is not None
    return skill in low_text


def _match_skills(text: str) -> List[str]:
    low = text.lower()
    seen = set()
    result = []
    for skill in SKILL_KEYWORDS:
        if skill not in seen and _skill_present(skill, low):
            seen.add(skill)
            result.append(skill)
    return result


def _detect_sector(text: str) -> Optional[str]:
    low = text.lower()
    best, best_hits = None, 0
    for sector, kws in SECTOR_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in low)
        if hits > best_hits:
            best, best_hits = sector, hits
    return best


def _detect_education(text: str) -> Optional[str]:
    low = text.lower()
    for pattern, label in EDUCATION_LEVELS:
        if re.search(pattern, low):
            return label
    return None


def _detect_location(text: str) -> Optional[str]:
    low = text.lower()
    for loc in LOCATIONS:
        if loc in low:
            return loc.title()
    return None


def _detect_experience_years(text: str) -> Optional[int]:
    low = text.lower()
    years = []
    for m in re.finditer(r"(\d{1,2})\s*(?:\+)?\s*(?:ans?|years?|année?s?)", low):
        try:
            years.append(int(m.group(1)))
        except ValueError:
            continue
    return max(years) if years else None


def _detect_job_title(text: str) -> Optional[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines[:15]:
        low = ln.lower()
        if len(ln) <= 60 and any(h in low for h in JOB_TITLE_HINTS):
            return ln
    return None


def _detect_name(text: str) -> Optional[str]:
    for ln in [l.strip() for l in text.splitlines() if l.strip()][:8]:
        if "@" in ln or any(ch.isdigit() for ch in ln):
            continue
        words = ln.split()
        if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
            if len(ln) <= 50:
                return ln
    return None


def analyze_cv_text(text: str) -> Dict[str, Any]:
    """Extract structured profile fields from raw CV text (deterministic)."""
    email_m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone_m = re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text)
    skills = _match_skills(text)

    return {
        "full_name": _detect_name(text),
        "email": email_m.group(0) if email_m else None,
        "phone": phone_m.group(0).strip() if phone_m else None,
        "skills": ", ".join(skills) if skills else None,
        "experience_years": _detect_experience_years(text),
        "education": _detect_education(text),
        "sector": _detect_sector(text),
        "job_title": _detect_job_title(text),
        "location": _detect_location(text),
        "profile_summary": _build_summary(text, skills),
    }


def _build_summary(text: str, skills: List[str]) -> str:
    years = _detect_experience_years(text)
    sector = _detect_sector(text)
    bits = []
    if sector:
        bits.append(f"Profil orienté {sector}")
    if years:
        bits.append(f"environ {years} ans d'expérience")
    if skills:
        bits.append(f"compétences clés : {', '.join(skills[:5])}")
    if not bits:
        return "Profil extrait automatiquement du CV (analyse locale)."
    return ". ".join(s[0].upper() + s[1:] for s in bits) + "."


def score_profile_job(profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a deterministic compatibility score (0-100) between profile and job."""
    profile_skills = _tokens(profile.get("skills"))
    req_text = " ".join(str(job.get(k, "")) for k in ("requirements", "description", "title"))
    req_keywords = _tokens(job.get("requirements")) or _tokens(req_text)
    all_job_tokens = _tokens(req_text)

    matched = sorted((profile_skills & all_job_tokens))
    skill_ratio = (len(profile_skills & req_keywords) / len(req_keywords)) if req_keywords else 0.0
    skill_pts = round(min(1.0, skill_ratio) * 55)

    # Sector
    p_sector = _tokens(profile.get("sector"))
    j_sector = _tokens(job.get("sector"))
    sector_match = bool(p_sector & j_sector)
    sector_pts = 20 if sector_match else (8 if (p_sector and matched) else 0)

    # Location
    p_loc = _tokens(profile.get("location"))
    j_loc = _tokens(job.get("location"))
    location_match = bool(p_loc & j_loc)
    location_pts = 15 if location_match else 0

    # Experience (no required years available → reward having experience)
    years = profile.get("experience_years") or 0
    try:
        years = int(years)
    except (TypeError, ValueError):
        years = 0
    exp_pts = min(10, years * 2)

    score = max(5, min(100, skill_pts + sector_pts + location_pts + exp_pts))

    strengths: List[str] = []
    if matched:
        strengths.append(f"Compétences correspondantes : {', '.join(matched[:4])}")
    if sector_match:
        strengths.append(f"Expérience dans le secteur {job.get('sector')}")
    if location_match:
        strengths.append(f"Localisation compatible ({job.get('location')})")
    if years:
        strengths.append(f"{years} an(s) d'expérience professionnelle")
    if not strengths:
        strengths.append("Profil exploitable pour ce poste")

    gaps: List[str] = []
    missing = [k for k in (req_keywords - profile_skills) if len(k) > 2][:3]
    if missing:
        gaps.append(f"Compétences à renforcer : {', '.join(missing)}")
    if not sector_match:
        gaps.append(f"Secteur du poste ({job.get('sector') or 'non précisé'}) différent de votre profil")
    if not location_match and j_loc:
        gaps.append(f"Poste situé à {job.get('location')}")
    if not gaps:
        gaps.append("Aucun écart majeur détecté")

    summary = (
        f"Compatibilité estimée à {score}% (analyse locale). "
        + ("Bonne correspondance des compétences. " if skill_ratio >= 0.5
           else "Correspondance partielle des compétences. ")
        + ("Secteur aligné." if sector_match else "Secteur à confirmer.")
    )

    return {"score": score, "strengths": strengths, "gaps": gaps, "summary": summary}
