"""
Génération de CV optimisé ATS, adapté à une offre d'emploi.

Principe : à partir du profil déjà analysé du candidat (compétences, expérience,
formation…) et d'une offre cible, on produit un CV mono-colonne, sans tableaux ni
images, avec les sections standard et les mots-clés de l'offre mis en avant — un
format lisible par les ATS (Applicant Tracking Systems).

Hybride, comme l'analyse de CV :
- moteur LOCAL sans clé (templating + extraction de mots-clés),
- bascule automatique vers l'IA pour rédiger une accroche plus fine si
  `APP_AI_BASE_URL` + `APP_AI_KEY` sont configurés (sinon repli local).

Compatible Python 3.9.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from core.config import settings
from schemas.aihub import ChatMessage, GenTxtRequest
from services import cv_heuristic, local_storage
from services.aihub import AIHubService

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Lecture du CV uploadé + découpage en sections (enrichissement)
# --------------------------------------------------------------------------- #
def load_cv_text(cv_object_key: Optional[str]) -> str:
    """Texte brut du CV PDF stocké localement (bucket 'cvs'). '' si indisponible."""
    if not cv_object_key:
        return ""
    try:
        import fitz  # PyMuPDF (déjà utilisé par cv_heuristic)

        path = local_storage.resolve_blob_path("cvs", cv_object_key)
        if not path.exists():
            return ""
        parts: List[str] = []
        with fitz.open(str(path)) as doc:
            for page in doc:
                parts.append(page.get_text())
        return "\n".join(parts)
    except Exception as exc:  # noqa: BLE001 - enrichissement best-effort
        logger.warning("Lecture du CV %s impossible: %s", cv_object_key, exc)
        return ""


# Mots-clés d'en-tête de section → clé canonique (sans accents, minuscule).
_SECTION_HEADERS = [
    ("experience", ["experience professionnelle", "experiences professionnelles", "experience",
                    "experiences", "parcours professionnel", "parcours", "emplois"]),
    ("education", ["formation", "formations", "education", "diplomes", "etudes", "cursus"]),
    ("skills", ["competences", "competences techniques", "skills", "savoir-faire",
                "outils", "technologies", "outils & technologies", "outils et technologies",
                "logiciels", "competences cles"]),
    ("languages", ["langues", "languages"]),
    ("certifications", ["certifications", "certificats", "certification"]),
    ("summary", ["profil", "resume", "a propos", "objectif", "accroche", "presentation"]),
    ("interests", ["centres d'interet", "centre d'interet", "loisirs", "hobbies", "interets",
                   "engagements", "membership", "engagements & membership", "vie associative",
                   "benevolat", "associatif"]),
    # Catégorie "autre": reconnue uniquement pour BORNER les sections précédentes
    # (non rendue dans le CV), afin d'éviter qu'elle déborde dans Langues/Certifs.
    ("other", ["references", "reference", "informations complementaires", "informations",
               "contact", "coordonnees", "divers"]),
]


def _strip_accents_lower(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in norm if not unicodedata.combining(c)).lower().strip()


def _match_header(line: str) -> Optional[str]:
    """Si la ligne est un en-tête de section connu, renvoie sa clé canonique."""
    norm = _strip_accents_lower(line).strip(" :-•|").strip()
    if not norm or len(norm) > 40:
        return None
    for key, variants in _SECTION_HEADERS:
        for v in variants:
            if norm == v or norm.startswith(v + " ") or norm == v + " :":
                return key
    return None


def parse_cv_sections(text: str) -> Dict[str, str]:
    """Découpe le texte du CV en sections (experience, education, languages, …)."""
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = _match_header(line)
        if header:
            current = header
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


# --------------------------------------------------------------------------- #
# Extraction / correspondance de mots-clés
# --------------------------------------------------------------------------- #
def _split_skills(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[,;/\n]", raw)
    out, seen = [], set()
    for p in parts:
        s = p.strip()
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def extract_job_keywords(job: Dict[str, Any]) -> List[str]:
    """Compétences/mots-clés saillants de l'offre (titre + exigences + description)."""
    text = " ".join(
        str(job.get(k) or "")
        for k in ("title", "requirements", "description", "sector")
    ).lower()
    found: List[str] = []
    for skill in cv_heuristic.SKILL_KEYWORDS:
        if cv_heuristic._skill_present(skill, text) and skill not in found:
            found.append(skill)
    return found


def match_profile_to_job(profile_skills: List[str], job: Dict[str, Any]) -> Dict[str, List[str]]:
    """Sépare les compétences du candidat en (correspondantes / autres) vis-à-vis de
    l'offre, et liste les mots-clés de l'offre absents du profil (à valoriser)."""
    job_text = " ".join(
        str(job.get(k) or "") for k in ("title", "requirements", "description", "sector")
    ).lower()
    job_keywords = extract_job_keywords(job)

    matched, others = [], []
    for sk in profile_skills:
        low = sk.lower()
        if low in job_text or any(low in kw or kw in low for kw in job_keywords):
            matched.append(sk)
        else:
            others.append(sk)

    profile_low = " ".join(profile_skills).lower()
    missing = [kw for kw in job_keywords if kw not in profile_low]
    return {"matched": matched, "others": others, "missing": missing}


# --------------------------------------------------------------------------- #
# Construction du contenu structuré
# --------------------------------------------------------------------------- #
def _local_summary(profile: Dict[str, Any], job: Dict[str, Any], matched: List[str]) -> str:
    bits: List[str] = []
    years = profile.get("experience_years")
    sector = profile.get("sector")
    target = job.get("title") or "le poste visé"
    company = job.get("company")

    head = "Professionnel"
    if years:
        head += f" avec {years} an(s) d'expérience"
    if sector:
        head += f" dans le secteur {sector}"
    head += f", candidat au poste de {target}"
    if company:
        head += f" chez {company}"
    bits.append(head + ".")

    if matched:
        bits.append("Compétences clés alignées avec l'offre : " + ", ".join(matched[:8]) + ".")
    existing = (profile.get("profile_summary") or "").strip()
    if existing:
        bits.append(existing)
    return " ".join(bits)


def _section_to_bullets(block: str, limit: int = 12) -> List[str]:
    """Transforme un bloc texte de section en puces (1 ligne = 1 puce)."""
    bullets: List[str] = []
    for line in (block or "").splitlines():
        s = line.strip(" \t-•*–·").strip()
        if len(s) >= 3:
            bullets.append(s)
        if len(bullets) >= limit:
            break
    return bullets


def build_cv_content(
    profile: Dict[str, Any],
    job: Dict[str, Any],
    summary_override: Optional[str] = None,
    cv_sections: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Assemble le contenu structuré du CV ATS."""
    cv_sections = cv_sections or {}
    profile_skills = _split_skills(profile.get("skills"))
    match = match_profile_to_job(profile_skills, job)
    matched, others = match["matched"], match["others"]

    summary = summary_override or _local_summary(profile, job, matched)

    # Compétences : correspondantes d'abord, puis le reste.
    skills_ordered = matched + others

    # Mots-clés ATS : compétences correspondantes + intitulé du poste cible.
    ats_keywords: List[str] = []
    for kw in matched + [w for w in re.split(r"\W+", str(job.get("title") or "")) if len(w) > 2]:
        k = kw.strip()
        if k and k.lower() not in {x.lower() for x in ats_keywords}:
            ats_keywords.append(k)

    # Enrichissement depuis le CV uploadé (contenu réel).
    experience_entries = _section_to_bullets(cv_sections.get("experience", ""), limit=30)
    education_detail = cv_sections.get("education", "").strip()
    languages = _section_to_bullets(cv_sections.get("languages", ""), limit=6)
    certifications = _section_to_bullets(cv_sections.get("certifications", ""), limit=8)
    # On garde "Compétences clés" courtes (issues de l'analyse). Les compétences
    # détaillées du CV sont déjà reflétées dans la section Expérience; on ne récupère
    # ici que les éventuels mots-clés COURTS absents du profil (évite les phrases).
    for sk in _split_skills(cv_sections.get("skills", "").replace("\n", ", ")):
        clean = sk.strip(" \t-•*–·").strip()
        if 2 <= len(clean) <= 28 and clean.lower() not in {s.lower() for s in skills_ordered}:
            skills_ordered.append(clean)

    return {
        "full_name": (profile.get("full_name") or "Candidat").strip(),
        "target_title": (job.get("title") or profile.get("job_title") or "").strip(),
        "target_company": (job.get("company") or "").strip(),
        "contact": {
            "email": (profile.get("email") or "").strip(),
            "phone": (profile.get("phone") or "").strip(),
            "location": (profile.get("location") or job.get("location") or "").strip(),
        },
        "summary": summary,
        "skills": skills_ordered,
        "current_title": (profile.get("job_title") or "").strip(),
        "experience_years": profile.get("experience_years"),
        "sector": (profile.get("sector") or "").strip(),
        "experience_entries": experience_entries,
        "education": education_detail or (profile.get("education") or "").strip(),
        "languages": languages,
        "certifications": certifications,
        "ats_keywords": ats_keywords[:20],
        "missing_keywords": match["missing"][:10],
    }


# --------------------------------------------------------------------------- #
# Rendu PDF ATS (mono-colonne, polices standard, pas de tableau/image)
# --------------------------------------------------------------------------- #
# Modèles de CV (couleurs + densité). "sobre" reste fidèle à un CV ATS classique
# (mono-colonne, noir/gris) comme un bon CV ATS de référence.
TEMPLATES = {
    "sobre": {"accent": "#1a1a1a", "name": "#111111", "rule": "#cccccc", "scale": 1.0},
    "bleu": {"accent": "#1d4ed8", "name": "#1d4ed8", "rule": "#bfdbfe", "scale": 1.0},
    "compact": {"accent": "#1a1a1a", "name": "#111111", "rule": "#cccccc", "scale": 0.88},
    # Calqué sur le CV d'Emmanuel: bleu nuit pour nom/titres/employeurs, gris pour
    # sous-titre et dates (palette Carlito #1f4e79 / #595959, police Carlito).
    "mon_cv": {"accent": "#1f4e79", "name": "#1f4e79", "rule": "#1f4e79", "scale": 1.0,
               "subtitle": "#595959", "date": "#595959", "font": "Carlito"},
}
DEFAULT_TEMPLATE = "sobre"

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_CARLITO_REGISTERED: Optional[bool] = None


def _register_carlito() -> bool:
    """Enregistre la famille Carlito (téléchargée dans assets/fonts). Idempotent."""
    global _CARLITO_REGISTERED
    if _CARLITO_REGISTERED is not None:
        return _CARLITO_REGISTERED
    try:
        files = {
            "Carlito": "Carlito-Regular.ttf",
            "Carlito-Bold": "Carlito-Bold.ttf",
            "Carlito-Italic": "Carlito-Italic.ttf",
            "Carlito-BoldItalic": "Carlito-BoldItalic.ttf",
        }
        for name, fn in files.items():
            path = _FONT_DIR / fn
            if not path.exists():
                _CARLITO_REGISTERED = False
                return False
            pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily(
            "Carlito", normal="Carlito", bold="Carlito-Bold",
            italic="Carlito-Italic", boldItalic="Carlito-BoldItalic",
        )
        _CARLITO_REGISTERED = True
    except Exception as exc:  # noqa: BLE001 - repli Helvetica
        logger.warning("Enregistrement Carlito échoué: %s", exc)
        _CARLITO_REGISTERED = False
    return _CARLITO_REGISTERED


def _fonts(tpl: Dict[str, Any]) -> Dict[str, str]:
    """Jeu de polices (regular/bold/italic) du modèle, avec repli Helvetica."""
    if tpl.get("font") == "Carlito" and _register_carlito():
        return {"regular": "Carlito", "bold": "Carlito-Bold", "italic": "Carlito-Italic"}
    return {"regular": "Helvetica", "bold": "Helvetica-Bold", "italic": "Helvetica-Oblique"}


def _template(name: Optional[str]) -> Dict[str, Any]:
    return TEMPLATES.get((name or "").strip().lower(), TEMPLATES[DEFAULT_TEMPLATE])


def _styles(tpl: Dict[str, Any]):
    base = getSampleStyleSheet()
    s = tpl.get("scale", 1.0)
    f = _fonts(tpl)
    styles = {
        "name": ParagraphStyle("name", parent=base["Title"], fontName=f["bold"],
                               fontSize=20 * s, leading=24 * s, spaceAfter=2, alignment=TA_LEFT,
                               textColor=tpl["name"]),
        "title": ParagraphStyle("ttl", parent=base["Normal"], fontName=f["regular"],
                                fontSize=12 * s, leading=15 * s, textColor=tpl.get("subtitle", "#333333"),
                                spaceAfter=4),
        "exp_header": ParagraphStyle("exph", parent=base["Normal"], fontName=f["bold"],
                                     fontSize=10.5 * s, leading=14 * s, textColor=tpl["accent"],
                                     spaceBefore=4, spaceAfter=1),
        "exp_date": ParagraphStyle("expd", parent=base["Normal"], fontName=f["italic"],
                                   fontSize=9 * s, leading=12 * s, textColor=tpl.get("date", "#595959"),
                                   spaceAfter=2),
        "contact": ParagraphStyle("contact", parent=base["Normal"], fontName=f["regular"],
                                  fontSize=9.5 * s, leading=13 * s, textColor="#444444", spaceAfter=6),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName=f["bold"],
                                  fontSize=11.5 * s, leading=14 * s, textColor=tpl["accent"],
                                  spaceBefore=10 * s, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName=f["regular"],
                              fontSize=10 * s, leading=14 * s, spaceAfter=3),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontName=f["regular"],
                                fontSize=10 * s, leading=14 * s),
    }
    return styles


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_DATE_LINE_RE = re.compile(r"((19|20)\d{2}|aujourd'?hui|present|présent)", re.I)


def _classify_exp_line(line: str) -> str:
    """Catégorise une ligne d'expérience: 'date', 'header' (employeur/poste) ou 'bullet'."""
    if len(line) <= 80 and _DATE_LINE_RE.search(line):
        return "date"
    if len(line) <= 80 and "|" in line:
        return "header"
    alpha = [c for c in line if c.isalpha()]
    if alpha and len(line) <= 70:
        upper_ratio = sum(c.isupper() for c in alpha) / len(alpha)
        if upper_ratio >= 0.6:
            return "header"
    return "bullet"


def build_pdf(content: Dict[str, Any], template: Optional[str] = None) -> bytes:
    """Génère le PDF ATS et renvoie ses octets."""
    tpl = _template(template)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title="CV - %s" % content.get("full_name", ""),
    )
    st = _styles(tpl)
    flow: List[Any] = []

    # En-tête
    flow.append(Paragraph(_esc(content["full_name"]), st["name"]))
    if content.get("target_title"):
        flow.append(Paragraph(_esc("Candidature : %s" % content["target_title"]), st["title"]))
    c = content["contact"]
    contact_line = "  •  ".join(x for x in [c.get("email"), c.get("phone"), c.get("location")] if x)
    if contact_line:
        flow.append(Paragraph(_esc(contact_line), st["contact"]))
    flow.append(HRFlowable(width="100%", thickness=0.8, color=tpl["rule"], spaceAfter=4))

    def section(title: str):
        flow.append(Paragraph(title.upper(), st["section"]))

    # Accroche
    if content.get("summary"):
        section("Profil")
        flow.append(Paragraph(_esc(content["summary"]), st["body"]))

    # Compétences
    if content.get("skills"):
        section("Compétences clés")
        flow.append(Paragraph(_esc(" • ".join(content["skills"][:18])), st["body"]))

    # Expérience professionnelle
    exp_bits = []
    if content.get("current_title"):
        exp_bits.append(content["current_title"])
    if content.get("sector"):
        exp_bits.append(content["sector"])
    if content.get("experience_years"):
        exp_bits.append("%s an(s) d'expérience" % content["experience_years"])
    experience_entries = content.get("experience_entries") or []
    if exp_bits or experience_entries:
        section("Expérience professionnelle")
        if exp_bits:
            flow.append(Paragraph("<b>%s</b>" % _esc(" — ".join(exp_bits)), st["body"]))
        if experience_entries:
            # Contenu réel issu du CV uploadé : employeur en gras, dates en italique
            # gris, descriptions en puces (proche de la mise en page d'un vrai CV).
            bullet_buffer: List[str] = []

            def _flush_bullets():
                if bullet_buffer:
                    items = [ListItem(Paragraph(_esc(b), st["bullet"]), leftIndent=8) for b in bullet_buffer]
                    flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=10))
                    bullet_buffer.clear()

            for line in experience_entries:
                kind = _classify_exp_line(line)
                if kind == "header":
                    _flush_bullets()
                    flow.append(Paragraph("<b>%s</b>" % _esc(line), st["exp_header"]))
                elif kind == "date":
                    _flush_bullets()
                    flow.append(Paragraph(_esc(line), st["exp_date"]))
                else:
                    bullet_buffer.append(line)
            _flush_bullets()
        else:
            # Pas de section "Expérience" détectée dans le CV → invites à compléter.
            items = [
                ListItem(Paragraph(_esc(b), st["bullet"]), leftIndent=8)
                for b in [
                    "Réalisations et responsabilités en lien avec le poste visé : [à compléter].",
                    "Résultats quantifiés (chiffres, %, délais) : [à compléter].",
                ]
            ]
            flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=10))

    # Formation
    if content.get("education"):
        section("Formation")
        edu_lines = [l.strip(" \t-•*–·").strip() for l in str(content["education"]).splitlines()]
        edu_lines = [l for l in edu_lines if l]
        if len(edu_lines) > 1:
            items = [ListItem(Paragraph(_esc(l), st["bullet"]), leftIndent=8) for l in edu_lines[:8]]
            flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=10))
        else:
            flow.append(Paragraph(_esc(content["education"]), st["body"]))

    # Certifications
    if content.get("certifications"):
        section("Certifications")
        items = [ListItem(Paragraph(_esc(b), st["bullet"]), leftIndent=8) for b in content["certifications"]]
        flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=10))

    # Langues
    if content.get("languages"):
        section("Langues")
        flow.append(Paragraph(_esc(" • ".join(content["languages"])), st["body"]))

    # Mots-clés ATS
    if content.get("ats_keywords"):
        section("Mots-clés")
        flow.append(Paragraph(_esc(", ".join(content["ats_keywords"])), st["body"]))

    doc.build(flow)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Lettre de motivation
# --------------------------------------------------------------------------- #
def _local_cover_letter_body(profile: Dict[str, Any], job: Dict[str, Any], matched: List[str]) -> List[str]:
    """Corps de lettre (liste de paragraphes) — moteur local sans clé."""
    title = job.get("title") or "le poste proposé"
    company = job.get("company") or "votre entreprise"
    years = profile.get("experience_years")
    sector = profile.get("sector")
    current = profile.get("job_title")

    p1 = (
        f"Actuellement {current} " if current else "Professionnel "
    ) + (
        f"fort de {years} an(s) d'expérience" if years else "motivé"
    ) + (
        f" dans le secteur {sector}" if sector else ""
    ) + f", je vous soumets ma candidature au poste de {title} au sein de {company}."

    if matched:
        p2 = (
            "Mon parcours m'a permis de développer des compétences directement utiles à ce poste, "
            f"notamment : {', '.join(matched[:6])}. "
            "Rigoureux et orienté résultats, je suis convaincu de pouvoir contribuer rapidement à vos objectifs."
        )
    else:
        p2 = (
            "Rigoureux, autonome et orienté résultats, je suis convaincu que mon profil correspond aux "
            "attentes de ce poste et que je saurai contribuer rapidement à vos objectifs."
        )

    p3 = (
        f"Vivement intéressé par l'opportunité de rejoindre {company}, je me tiens à votre disposition "
        "pour un entretien afin de vous exposer ma motivation. Dans l'attente de votre retour, je vous prie "
        "d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées."
    )
    return [p1, p2, p3]


def build_cover_letter_content(
    profile: Dict[str, Any], job: Dict[str, Any], date_str: str = "",
    body_override: Optional[List[str]] = None,
) -> Dict[str, Any]:
    profile_skills = _split_skills(profile.get("skills"))
    matched = match_profile_to_job(profile_skills, job)["matched"]
    return {
        "full_name": (profile.get("full_name") or "Candidat").strip(),
        "contact": {
            "email": (profile.get("email") or "").strip(),
            "phone": (profile.get("phone") or "").strip(),
            "location": (profile.get("location") or "").strip(),
        },
        "company": (job.get("company") or "").strip(),
        "target_title": (job.get("title") or "").strip(),
        "date_str": date_str,
        "paragraphs": body_override or _local_cover_letter_body(profile, job, matched),
    }


def build_cover_letter_pdf(content: Dict[str, Any], template: Optional[str] = None) -> bytes:
    tpl = _template(template)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
        title="Lettre de motivation - %s" % content.get("full_name", ""),
    )
    st = _styles(tpl)
    letter_body = ParagraphStyle("letter", parent=st["body"], spaceAfter=10, leading=15)
    flow: List[Any] = []

    # Expéditeur
    flow.append(Paragraph(_esc(content["full_name"]), st["name"]))
    c = content["contact"]
    contact_line = "  •  ".join(x for x in [c.get("email"), c.get("phone"), c.get("location")] if x)
    if contact_line:
        flow.append(Paragraph(_esc(contact_line), st["contact"]))
    flow.append(Spacer(1, 8))

    # Destinataire + date
    if content.get("company"):
        flow.append(Paragraph(_esc("À l'attention de %s" % content["company"]), st["body"]))
    place_date = []
    if c.get("location"):
        place_date.append(content["contact"]["location"])
    if content.get("date_str"):
        place_date.append("le %s" % content["date_str"])
    if place_date:
        flow.append(Paragraph(_esc(", ".join(place_date)), st["body"]))
    flow.append(Spacer(1, 10))

    # Objet
    if content.get("target_title"):
        flow.append(Paragraph("<b>Objet : Candidature au poste de %s</b>" % _esc(content["target_title"]), st["body"]))
        flow.append(Spacer(1, 8))

    # Salutation + corps
    flow.append(Paragraph("Madame, Monsieur,", letter_body))
    for para in content.get("paragraphs", []):
        flow.append(Paragraph(_esc(para), letter_body))

    # Signature
    flow.append(Spacer(1, 12))
    flow.append(Paragraph(_esc(content["full_name"]), st["body"]))

    doc.build(flow)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Service (hybride local / IA)
# --------------------------------------------------------------------------- #
class CvGeneratorService:
    def __init__(self):
        self.ai_service = AIHubService()
        self.ai_available = bool(
            getattr(settings, "app_ai_base_url", "") and getattr(settings, "app_ai_key", "")
        )

    async def _ai_summary(self, profile: Dict[str, Any], job: Dict[str, Any], matched: List[str]) -> Optional[str]:
        prompt = (
            "Rédige une accroche de CV (3 à 4 phrases, en français, à la 1re personne implicite, "
            "sans liste) pour un candidat postulant à cette offre. Mets en avant les compétences "
            "pertinentes et l'adéquation au poste. Réponds UNIQUEMENT par le texte de l'accroche.\n\n"
            f"POSTE: {job.get('title')} chez {job.get('company')} (secteur {job.get('sector')})\n"
            f"EXIGENCES: {job.get('requirements')}\n"
            f"CANDIDAT: {profile.get('job_title')}, {profile.get('experience_years')} an(s) d'expérience, "
            f"formation {profile.get('education')}. Compétences correspondantes: {', '.join(matched)}."
        )
        request = GenTxtRequest(
            messages=[
                ChatMessage(role="system", content="Tu es un coach carrière expert en CV ATS."),
                ChatMessage(role="user", content=prompt),
            ],
            model="deepseek-v4-pro",
        )
        response = await self.ai_service.gentxt(request)
        text = (response.content or "").strip()
        return text or None

    async def generate(self, profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
        """Construit le contenu du CV, enrichi par le CV uploadé (accroche IA si dispo)."""
        # Enrichissement : lire et découper le CV PDF réellement uploadé.
        cv_text = load_cv_text(profile.get("cv_object_key"))
        cv_sections = parse_cv_sections(cv_text) if cv_text else {}

        summary_override = None
        if self.ai_available:
            try:
                profile_skills = _split_skills(profile.get("skills"))
                matched = match_profile_to_job(profile_skills, job)["matched"]
                summary_override = await self._ai_summary(profile, job, matched)
            except Exception as exc:  # noqa: BLE001 - repli local
                logger.warning("AI CV summary failed (%s); using local summary", exc)
        return build_cv_content(profile, job, summary_override=summary_override, cv_sections=cv_sections)

    async def _ai_cover_letter(self, profile: Dict[str, Any], job: Dict[str, Any], matched: List[str]) -> Optional[List[str]]:
        prompt = (
            "Rédige le CORPS d'une lettre de motivation en français (3 paragraphes, ton professionnel, "
            "1re personne), pour ce candidat et cette offre. N'inclus NI l'en-tête, NI la date, NI 'Madame, Monsieur', "
            "NI la signature — uniquement les 3 paragraphes séparés par une ligne vide.\n\n"
            f"POSTE: {job.get('title')} chez {job.get('company')} (secteur {job.get('sector')})\n"
            f"EXIGENCES: {job.get('requirements')}\n"
            f"CANDIDAT: {profile.get('job_title')}, {profile.get('experience_years')} an(s) d'expérience. "
            f"Compétences correspondantes: {', '.join(matched)}."
        )
        request = GenTxtRequest(
            messages=[
                ChatMessage(role="system", content="Tu es un coach carrière expert en lettres de motivation."),
                ChatMessage(role="user", content=prompt),
            ],
            model="deepseek-v4-pro",
        )
        response = await self.ai_service.gentxt(request)
        text = (response.content or "").strip()
        if not text:
            return None
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return paras or None

    async def generate_cover_letter(
        self, profile: Dict[str, Any], job: Dict[str, Any], date_str: str = ""
    ) -> Dict[str, Any]:
        """Construit le contenu de la lettre de motivation (corps IA si dispo, sinon local)."""
        body_override = None
        if self.ai_available:
            try:
                profile_skills = _split_skills(profile.get("skills"))
                matched = match_profile_to_job(profile_skills, job)["matched"]
                body_override = await self._ai_cover_letter(profile, job, matched)
            except Exception as exc:  # noqa: BLE001 - repli local
                logger.warning("AI cover letter failed (%s); using local body", exc)
        return build_cover_letter_content(profile, job, date_str=date_str, body_override=body_override)
