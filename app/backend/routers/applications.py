"""Candidature en 1 clic, préparée par l'IA et validée par le candidat.

- `GET  /api/v1/applications/prepare?job_id=` → canal d'envoi possible + lettre
  pré-rédigée (IA si dispo, sinon moteur local) que le candidat relit et modifie.
- `POST /api/v1/applications/send`            → génère le CV adapté + la lettre
  (PDF) et les envoie par e-mail au recruteur, avec le candidat en Reply-To et en
  copie cachée (preuve d'envoi). Marque l'offre « Postulé ».
- `GET  /api/v1/applications/mine`            → historique des envois.

Canaux :
- `recruiter` : offre publiée et approuvée sur EmploiCentral → e-mail du compte
  recruteur + notification in-app.
- `email`     : adresse de candidature trouvée dans le texte de l'annonce.
- `external`  : l'annonce renvoie vers son site d'origine (formulaire propre) →
  pas d'envoi automatique ; le front propose CV + lettre prêts et ouvre le lien.

Rien ne part sans un clic explicite du candidat : jamais d'envoi en masse.
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from datetime import datetime
from html import escape
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.auth import User
from models.job_applications import Job_applications
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from models.notifications import Notification
from models.user_jobs import User_jobs
from models.user_profiles import User_profiles
from schemas.auth import UserResponse
from services.cv_generator import (
    CvGeneratorService,
    build_cover_letter_content,
    build_cover_letter_pdf,
    build_pdf,
    clean_job_title,
    poste_de,
)
from services.notifications import send_email_with_attachments

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])

# Garde-fou anti-spam : nombre d'envois par candidat et par jour.
DAILY_LIMIT = int(os.environ.get("APPLY_DAILY_LIMIT") or 15)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Adresses de plateformes/robots : jamais des adresses de candidature.
_IGNORED_EMAIL_RE = re.compile(
    r"(no-?reply|ne-?pas-?repondre|example\.|@(emploi\.(ci|tg)|novojob|afriqueemplois|"
    r"talent-tectra|linkedin|sentry))",
    re.I,
)


def find_contact_email(*texts: Optional[str]) -> Optional[str]:
    """Première adresse de candidature exploitable dans le texte d'une annonce."""
    for text in texts:
        for m in _EMAIL_RE.findall(text or ""):
            addr = m.strip(".").lower()
            if not _IGNORED_EMAIL_RE.search(addr):
                return addr
    return None


class PrepareResponse(BaseModel):
    channel: str                       # recruiter | email | external | none
    recipient_label: Optional[str] = None
    source_url: Optional[str] = None
    subject: str
    paragraphs: List[str]
    ai_generated: bool = False
    already_sent_at: Optional[datetime] = None
    daily_remaining: int


class SendRequest(BaseModel):
    job_id: int
    template: Optional[str] = "mon_cv"
    paragraphs: List[str]


class SendResponse(BaseModel):
    ok: bool
    recipient_label: Optional[str] = None
    sent_at: Optional[datetime] = None


class ApplicationRow(BaseModel):
    id: int
    job_id: int
    job_title: Optional[str] = None
    company: Optional[str] = None
    channel: str
    status: str
    created_at: Optional[datetime] = None


async def _load(db: AsyncSession, user_id: str, job_id: int):
    profile = (await db.execute(
        select(User_profiles).where(User_profiles.user_id == user_id).order_by(User_profiles.id.desc())
    )).scalars().first()
    if not profile or not profile.cv_analyzed:
        raise HTTPException(status_code=400, detail="Analysez d'abord votre CV (page Profil).")
    job = (await db.execute(select(Job_offers).where(Job_offers.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    return profile, job


async def _resolve_channel(db: AsyncSession, job: Job_offers) -> dict:
    """Où (et si) l'envoi direct est possible pour cette offre."""
    posting = (await db.execute(
        select(Job_postings).where(Job_postings.job_id == job.id, Job_postings.status == "approved")
    )).scalars().first()
    if posting:
        rec = (await db.execute(select(User).where(User.id == posting.posted_by))).scalar_one_or_none()
        if rec and rec.email:
            return {"channel": "recruiter", "to": rec.email, "recruiter_id": rec.id,
                    "label": posting.company_name or job.company or "le recruteur"}
    addr = find_contact_email(job.description, job.requirements)
    if addr:
        return {"channel": "email", "to": addr, "label": addr}
    if job.source_url:
        return {"channel": "external", "label": job.source or None}
    return {"channel": "none", "label": None}


async def _sent_today(db: AsyncSession, user_id: str) -> int:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return (await db.execute(
        select(func.count(Job_applications.id)).where(
            Job_applications.user_id == user_id,
            Job_applications.status == "sent",
            Job_applications.created_at >= start,
        )
    )).scalar() or 0


async def _already_sent(db: AsyncSession, user_id: str, job_id: int) -> Optional[Job_applications]:
    return (await db.execute(
        select(Job_applications).where(
            Job_applications.user_id == user_id,
            Job_applications.job_id == job_id,
            Job_applications.status == "sent",
        ).order_by(Job_applications.id.desc())
    )).scalars().first()


def _profile_dict(p: User_profiles) -> dict:
    return {
        "full_name": p.full_name, "email": p.email, "phone": p.phone, "skills": p.skills,
        "experience_years": p.experience_years, "education": p.education, "sector": p.sector,
        "job_title": p.job_title, "location": p.location, "profile_summary": p.profile_summary,
        "cv_object_key": p.cv_object_key, "cv_text": p.cv_text,
    }


def _job_dict(j: Job_offers) -> dict:
    return {
        "title": j.title, "company": j.company, "sector": j.sector, "requirements": j.requirements,
        "description": j.description, "location": j.location,
    }


def _subject(job: Job_offers, full_name: str) -> str:
    title = clean_job_title(job.title, job.location)
    head = f"Candidature {poste_de(title)}" if title else "Candidature spontanée"
    return f"{head} — {full_name}".strip(" —")


def _ascii(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", norm).strip("_") or "candidat"


@router.get("/prepare", response_model=PrepareResponse)
async def prepare(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user.id)
    profile, job = await _load(db, uid, job_id)
    ch = await _resolve_channel(db, job)
    prev = await _already_sent(db, uid, job_id)
    remaining = max(0, DAILY_LIMIT - await _sent_today(db, uid))
    profile_data, job_data = _profile_dict(profile), _job_dict(job)
    full_name = (profile.full_name or current_user.name or "").strip()
    source_url = job.source_url
    subject = _subject(job, full_name)
    # Fin de transaction avant l'appel IA (lent). Un rollback expire les objets ORM :
    # tout ce qui sert ensuite a été copié ci-dessus.
    await db.rollback()

    service = CvGeneratorService()
    letter = await service.generate_cover_letter(profile_data, job_data)
    return PrepareResponse(
        channel=ch["channel"],
        recipient_label=ch.get("label"),
        source_url=source_url,
        subject=subject,
        paragraphs=letter["paragraphs"],
        ai_generated=service.ai_available,
        already_sent_at=prev.created_at if prev else None,
        daily_remaining=remaining,
    )


@router.post("/send", response_model=SendResponse)
async def send(
    data: SendRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user.id)
    profile, job = await _load(db, uid, data.job_id)
    paragraphs = [p.strip() for p in data.paragraphs if p and p.strip()]
    if not paragraphs:
        raise HTTPException(status_code=400, detail="La lettre de motivation est vide.")
    if sum(len(p) for p in paragraphs) > 6000:
        raise HTTPException(status_code=400, detail="La lettre est trop longue (6 000 caractères max).")

    candidate_email = (profile.email or current_user.email or "").strip()
    full_name = (profile.full_name or current_user.name or "").strip()
    if not (candidate_email and full_name):
        raise HTTPException(status_code=400, detail="Renseignez votre nom et votre e-mail dans le profil.")

    ch = await _resolve_channel(db, job)
    if ch["channel"] not in ("recruiter", "email"):
        raise HTTPException(status_code=400, detail="Cette offre se postule sur son site d'origine.")
    if await _already_sent(db, uid, job.id):
        raise HTTPException(status_code=409, detail="Vous avez déjà envoyé votre candidature pour cette offre.")
    if await _sent_today(db, uid) >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {DAILY_LIMIT} candidatures par jour atteinte. Réessayez demain.",
        )

    profile_data, job_data = _profile_dict(profile), _job_dict(job)
    subject = _subject(job, full_name)
    job_id, company = job.id, job.company
    job_title = clean_job_title(job.title, job.location)
    await db.rollback()  # objets ORM expirés après ceci : on n'utilise plus que les copies

    # Documents : CV adapté à l'offre + lettre telle que relue/modifiée par le candidat.
    service = CvGeneratorService()
    try:
        cv_content = await service.generate(profile_data, job_data)
        cv_pdf = build_pdf(cv_content, template=data.template)
        letter_content = build_cover_letter_content(
            profile_data, job_data, date_str=datetime.now().strftime("%d/%m/%Y"),
            body_override=paragraphs,
        )
        letter_pdf = build_cover_letter_pdf(letter_content, template=data.template)
    except Exception as exc:  # noqa: BLE001
        logger.error("Génération des documents de candidature échouée: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Génération du CV ou de la lettre échouée.")

    slug = _ascii(full_name)
    attachments = [
        (f"CV_{slug}.pdf", cv_pdf, "pdf"),
        (f"Lettre_de_motivation_{slug}.pdf", letter_pdf, "pdf"),
    ]
    body_html = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    contact = " · ".join(escape(x) for x in [candidate_email, profile_data.get("phone") or ""] if x)
    html = (
        "<p>Madame, Monsieur,</p>"
        f"{body_html}"
        f"<p>{escape(full_name)}<br>{contact}</p>"
        "<p>Vous trouverez ci-joints mon CV et ma lettre de motivation.</p>"
        "<hr><p style='color:#888;font-size:12px'>Candidature transmise via EmploiCentral. "
        "Pour répondre au candidat, utilisez simplement « Répondre ».</p>"
    )
    error = await send_email_with_attachments(
        ch["to"], subject, html, attachments,
        reply_to=candidate_email, from_name=f"{full_name} via EmploiCentral", bcc=candidate_email,
    )

    row = Job_applications(
        user_id=uid, job_id=job_id, channel=ch["channel"], recipient=ch["to"], subject=subject,
        letter="\n\n".join(paragraphs), cv_template=data.template,
        status="failed" if error else "sent", error=error,
    )
    db.add(row)
    if error:
        await db.commit()
        raise HTTPException(status_code=502, detail="L'e-mail n'a pas pu partir. Réessayez dans quelques minutes.")

    # Suivi : l'offre passe en « Postulé » (sans écraser Entretien / Rejeté).
    uj = (await db.execute(
        select(User_jobs).where(User_jobs.user_id == uid, User_jobs.job_id == job_id)
    )).scalars().first()
    if not uj:
        db.add(User_jobs(user_id=uid, job_id=job_id, saved=False, status="applied"))
    elif (uj.status or "") in ("", "to_apply"):
        uj.status = "applied"

    if ch["channel"] == "recruiter":
        db.add(Notification(
            user_id=ch["recruiter_id"], job_id=job_id,
            title=f"📩 Nouvelle candidature : {job_title or 'votre offre'}",
            body=f"{full_name} a postulé. CV et lettre envoyés à votre adresse e-mail.",
            channels="in_app,email", is_read=False,
        ))
    await db.commit()
    await db.refresh(row)
    logger.info("Candidature envoyée: user=%s job=%s canal=%s (%s)", uid, job_id, ch["channel"], company)
    return SendResponse(ok=True, recipient_label=ch.get("label"), sent_at=row.created_at)


@router.get("/mine", response_model=List[ApplicationRow])
async def mine(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Job_applications).where(Job_applications.user_id == str(current_user.id))
        .order_by(Job_applications.id.desc()).limit(200)
    )).scalars().all()
    jobs = {}
    if rows:
        jrows = (await db.execute(
            select(Job_offers).where(Job_offers.id.in_({r.job_id for r in rows}))
        )).scalars().all()
        jobs = {j.id: j for j in jrows}
    return [
        ApplicationRow(
            id=r.id, job_id=r.job_id,
            job_title=jobs[r.job_id].title if r.job_id in jobs else None,
            company=jobs[r.job_id].company if r.job_id in jobs else None,
            channel=r.channel, status=r.status, created_at=r.created_at,
        )
        for r in rows
    ]
