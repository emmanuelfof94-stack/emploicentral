"""
Espace recruteur : inscription dédiée, publication d'offres (modérées par l'admin),
suivi des candidats. Le contenu des offres vit dans `job_offers` (réutilise tout
l'existant) ; `job_postings` porte le propriétaire + l'état de modération.

Modération : une offre recruteur est créée `is_active=False` (invisible au feed
candidat) et le devient à l'approbation admin.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_admin_user, get_current_user
from models.analytics import PageView
from models.auth import User
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from models.job_views import Job_views
from models.recruiter_profiles import Recruiter_profiles
from models.user_jobs import User_jobs
from models.user_profiles import User_profiles
from schemas.auth import UserResponse
from services.auth import AuthService, validate_password_strength
from services.cv_heuristic import score_profile_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recruiter", tags=["recruiter"])


# ---------- Dépendance rôle ----------
async def get_recruiter_user(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if current_user.role not in ("recruiter", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Espace réservé aux recruteurs.")
    return current_user


# ---------- Schemas ----------
class RecruiterRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = None
    company_name: str
    contact_phone: Optional[str] = None


class AuthTokenResponse(BaseModel):
    token: str
    expires_at: int


class JobInput(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    valid_through: Optional[str] = None  # "YYYY-MM-DD"


class RecruiterJobRow(BaseModel):
    job_id: int
    posting_id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    status: str                # pending / approved / rejected
    is_active: Optional[bool] = None
    reject_reason: Optional[str] = None
    applicants: int = 0
    saves: int = 0
    created_at: Optional[datetime] = None


class CandidateRow(BaseModel):
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[str] = None       # to_apply / applied / interview / rejected
    saved: Optional[bool] = None
    cv_analyzed: Optional[bool] = None
    # Compatibilité profil ↔ offre (0-100), None si le candidat n'a pas de profil exploitable.
    score: Optional[int] = None
    strengths: List[str] = []


# ---------- Inscription recruteur ----------
@router.post("/register", response_model=AuthTokenResponse)
async def register_recruiter(payload: RecruiterRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Crée un compte recruteur (rôle 'recruiter' + profil entreprise) et renvoie un token."""
    auth_service = AuthService(db)
    # Mot de passe trop faible → 400 ; 409 reste réservé à « email déjà utilisé ».
    try:
        validate_password_strength(payload.password, payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    try:
        user = await auth_service.register_local_user(
            email=payload.email, password=payload.password, name=payload.name
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Promotion en recruteur (sauf si déjà admin via email admin).
    if user.role != "admin":
        user.role = "recruiter"
    db.add(Recruiter_profiles(
        user_id=user.id,
        company_name=(payload.company_name or "").strip() or None,
        contact_phone=(payload.contact_phone or "").strip() or None,
    ))
    await db.commit()

    app_token, expires_at, _ = await auth_service.issue_app_token(user=user)
    return AuthTokenResponse(token=app_token, expires_at=int(expires_at.timestamp()))


async def _company_for(db: AsyncSession, user_id: str) -> Optional[str]:
    prof = (await db.execute(
        select(Recruiter_profiles).where(Recruiter_profiles.user_id == user_id)
    )).scalars().first()
    return prof.company_name if prof else None


# ---------- Publication / gestion d'offres ----------
@router.post("/jobs", response_model=RecruiterJobRow, status_code=201)
async def create_job(
    data: JobInput,
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    title = (data.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Le titre est requis.")
    company = (data.company or "").strip() or (await _company_for(db, str(recruiter.id))) or "Entreprise"

    # Offre créée INACTIVE → invisible au feed candidat tant que non approuvée.
    job = Job_offers(
        title=title, company=company,
        location=(data.location or "").strip() or None,
        contract_type=(data.contract_type or "").strip() or None,
        sector=(data.sector or "").strip() or None,
        description=(data.description or "").strip() or None,
        requirements=(data.requirements or "").strip() or None,
        salary_range=(data.salary_range or "").strip() or None,
        valid_through=(data.valid_through or "").strip() or None,
        source="Recruteur", source_url=None,
        posted_date=datetime.now().strftime("%Y-%m-%d"),
        is_active=False,
    )
    db.add(job)
    await db.flush()  # récupère job.id

    posting = Job_postings(
        job_id=job.id, posted_by=str(recruiter.id),
        company_name=company, status="pending",
    )
    db.add(posting)
    await db.commit()
    await db.refresh(job)
    await db.refresh(posting)

    return RecruiterJobRow(
        job_id=job.id, posting_id=posting.id, title=job.title, company=job.company,
        location=job.location, contract_type=job.contract_type, status=posting.status,
        is_active=job.is_active, applicants=0, saves=0, created_at=posting.created_at,
    )


@router.get("/jobs", response_model=List[RecruiterJobRow])
async def my_jobs(
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    postings = (await db.execute(
        select(Job_postings).where(Job_postings.posted_by == str(recruiter.id))
        .order_by(Job_postings.id.desc())
    )).scalars().all()
    job_ids = [p.job_id for p in postings]
    jobs = {}
    counts: dict = {}
    if job_ids:
        jrows = (await db.execute(select(Job_offers).where(Job_offers.id.in_(job_ids)))).scalars().all()
        jobs = {j.id: j for j in jrows}
        # Compte candidatures (status non vide) et sauvegardes par offre.
        uj = (await db.execute(select(User_jobs).where(User_jobs.job_id.in_(job_ids)))).scalars().all()
        for u in uj:
            c = counts.setdefault(u.job_id, {"applicants": 0, "saves": 0})
            if (u.status or "").strip():
                c["applicants"] += 1
            if u.saved:
                c["saves"] += 1

    out: List[RecruiterJobRow] = []
    for p in postings:
        j = jobs.get(p.job_id)
        c = counts.get(p.job_id, {"applicants": 0, "saves": 0})
        out.append(RecruiterJobRow(
            job_id=p.job_id, posting_id=p.id,
            title=(j.title if j else "(offre supprimée)"),
            company=(j.company if j else p.company_name),
            location=(j.location if j else None),
            contract_type=(j.contract_type if j else None),
            status=p.status, is_active=(j.is_active if j else None),
            reject_reason=p.reject_reason,
            applicants=c["applicants"], saves=c["saves"], created_at=p.created_at,
        ))
    return out


async def _owned_posting(db: AsyncSession, job_id: int, user_id: str) -> Job_postings:
    posting = (await db.execute(
        select(Job_postings).where(
            Job_postings.job_id == job_id, Job_postings.posted_by == user_id
        )
    )).scalars().first()
    if not posting:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    return posting


@router.put("/jobs/{job_id}", response_model=RecruiterJobRow)
async def update_job(
    job_id: int,
    data: JobInput,
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    posting = await _owned_posting(db, job_id, str(recruiter.id))
    job = (await db.execute(select(Job_offers).where(Job_offers.id == job_id))).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable.")

    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        v = (value or "").strip() if isinstance(value, str) else value
        if key == "title" and not v:
            raise HTTPException(status_code=400, detail="Le titre est requis.")
        setattr(job, key, v or None)
    await db.commit()
    await db.refresh(job)
    return RecruiterJobRow(
        job_id=job.id, posting_id=posting.id, title=job.title, company=job.company,
        location=job.location, contract_type=job.contract_type, status=posting.status,
        is_active=job.is_active, reject_reason=posting.reject_reason,
        created_at=posting.created_at,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    posting = await _owned_posting(db, job_id, str(recruiter.id))
    job = (await db.execute(select(Job_offers).where(Job_offers.id == job_id))).scalars().first()
    if job:
        await db.delete(job)
    await db.delete(posting)
    await db.commit()
    return {"success": True}


@router.get("/jobs/{job_id}/candidates", response_model=List[CandidateRow])
async def job_candidates(
    job_id: int,
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    """Candidats ayant postulé ou sauvegardé cette offre (recruteur propriétaire),
    triés par score de compatibilité décroissant (candidatures avant simples sauvegardes
    à score égal)."""
    await _owned_posting(db, job_id, str(recruiter.id))
    job = (await db.execute(select(Job_offers).where(Job_offers.id == job_id))).scalars().first()

    uj = (await db.execute(select(User_jobs).where(User_jobs.job_id == job_id))).scalars().all()
    # On garde les interactions significatives (candidature OU sauvegarde).
    uj = [u for u in uj if (u.status or "").strip() or u.saved]
    user_ids = list({u.user_id for u in uj})
    profiles, users = {}, {}
    if user_ids:
        prows = (await db.execute(
            select(User_profiles).where(User_profiles.user_id.in_(user_ids))
        )).scalars().all()
        profiles = {p.user_id: p for p in prows}
        urows = (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u for u in urows}

    out: List[CandidateRow] = []
    for u in uj:
        p = profiles.get(u.user_id)
        usr = users.get(u.user_id)
        score, strengths = _score_candidate(p, job)
        out.append(CandidateRow(
            user_id=u.user_id,
            name=(p.full_name if p and p.full_name else None) or (usr.name if usr else None),
            email=(p.email if p and p.email else None) or (usr.email if usr else None),
            phone=(p.phone if p else None),
            location=(p.location if p else None),
            job_title=(p.job_title if p else None),
            status=u.status, saved=u.saved,
            cv_analyzed=(p.cv_analyzed if p else None),
            score=score, strengths=strengths,
        ))
    out.sort(key=lambda c: (c.score if c.score is not None else -1, bool((c.status or "").strip())), reverse=True)
    return out


def _score_candidate(profile: Optional[User_profiles], job: Optional[Job_offers]) -> tuple:
    """(score 0-100, points forts) — même moteur déterministe que les alertes candidats."""
    if not profile or not job or not (profile.skills or profile.sector or profile.job_title):
        return None, []
    try:
        r = score_profile_job(
            {"skills": profile.skills, "sector": profile.sector, "location": profile.location,
             "experience_years": profile.experience_years},
            {"title": job.title, "requirements": job.requirements, "description": job.description,
             "sector": job.sector, "location": job.location},
        )
        return int(r.get("score", 0)), list(r.get("strengths") or [])[:3]
    except Exception:  # noqa: BLE001 - le tri ne doit jamais casser la liste
        return None, []


# ---------- Modération admin ----------
class PendingPostingRow(BaseModel):
    posting_id: int
    job_id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    recruiter_email: Optional[str] = None
    created_at: Optional[datetime] = None


@router.get("/admin/pending", response_model=List[PendingPostingRow])
async def admin_pending(
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    postings = (await db.execute(
        select(Job_postings).where(Job_postings.status == "pending").order_by(Job_postings.id.desc())
    )).scalars().all()
    job_ids = [p.job_id for p in postings]
    recruiter_ids = list({p.posted_by for p in postings})
    jobs, recruiters = {}, {}
    if job_ids:
        jobs = {j.id: j for j in (await db.execute(
            select(Job_offers).where(Job_offers.id.in_(job_ids))
        )).scalars().all()}
    if recruiter_ids:
        recruiters = {u.id: u for u in (await db.execute(
            select(User).where(User.id.in_(recruiter_ids))
        )).scalars().all()}

    out: List[PendingPostingRow] = []
    for p in postings:
        j = jobs.get(p.job_id)
        r = recruiters.get(p.posted_by)
        out.append(PendingPostingRow(
            posting_id=p.id, job_id=p.job_id,
            title=(j.title if j else "(offre supprimée)"),
            company=(j.company if j else p.company_name),
            location=(j.location if j else None),
            sector=(j.sector if j else None),
            description=(j.description if j else None),
            requirements=(j.requirements if j else None),
            recruiter_email=(r.email if r else None),
            created_at=p.created_at,
        ))
    return out


class RejectInput(BaseModel):
    reason: Optional[str] = None


@router.post("/admin/{posting_id}/approve")
async def admin_approve(
    posting_id: int,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    posting = (await db.execute(
        select(Job_postings).where(Job_postings.id == posting_id)
    )).scalars().first()
    if not posting:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    job = (await db.execute(select(Job_offers).where(Job_offers.id == posting.job_id))).scalars().first()
    if job:
        job.is_active = True  # rend l'offre visible au feed candidat
    posting.status = "approved"
    posting.reject_reason = None
    await db.commit()
    return {"success": True}


@router.post("/admin/{posting_id}/reject")
async def admin_reject(
    posting_id: int,
    data: RejectInput,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    posting = (await db.execute(
        select(Job_postings).where(Job_postings.id == posting_id)
    )).scalars().first()
    if not posting:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    job = (await db.execute(select(Job_offers).where(Job_offers.id == posting.job_id))).scalars().first()
    if job:
        job.is_active = False
    posting.status = "rejected"
    posting.reject_reason = (data.reason or "").strip() or None
    await db.commit()
    return {"success": True}


# ---------- Contact candidat (Postuler via WhatsApp) ----------
class JobContact(BaseModel):
    company_name: Optional[str] = None
    whatsapp: Optional[str] = None     # chiffres internationaux sans '+' (format wa.me)


@router.get("/contact/{job_id}", response_model=JobContact)
async def job_contact(
    job_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Numéro WhatsApp du recruteur pour une offre APPROUVÉE (sinon vide).

    Réutilise `recruiter_profiles.contact_phone` saisi à l'inscription : aucune
    nouvelle colonne. Les offres agrégées n'ont pas de posting → réponse vide.
    """
    from services.notifications import _normalize_phone

    posting = (await db.execute(
        select(Job_postings).where(Job_postings.job_id == job_id, Job_postings.status == "approved")
    )).scalars().first()
    if not posting:
        return JobContact()
    # La fiche d'une offre recruteur appelle cette route à l'ouverture : c'est notre
    # compteur de vues dans l'appli (le recruteur qui consulte sa propre offre ne compte pas).
    if str(current_user.id) != posting.posted_by:
        await _record_view(db, job_id, str(current_user.id))
    prof = (await db.execute(
        select(Recruiter_profiles).where(Recruiter_profiles.user_id == posting.posted_by)
    )).scalars().first()
    phone = _normalize_phone(prof.contact_phone or "") if prof else ""
    return JobContact(
        company_name=posting.company_name or (prof.company_name if prof else None),
        whatsapp=phone.lstrip("+") or None,
    )


async def _record_view(db: AsyncSession, job_id: int, viewer_id: str) -> None:
    """Une vue par (offre, candidat, jour). Best-effort : n'empêche jamais la réponse."""
    day = datetime.now().strftime("%Y-%m-%d")
    try:
        exists = (await db.execute(select(Job_views.id).where(
            Job_views.job_id == job_id, Job_views.viewer_id == viewer_id, Job_views.day == day,
        ).limit(1))).first()
        if not exists:
            db.add(Job_views(job_id=job_id, viewer_id=viewer_id, day=day))
            await db.commit()
    except IntegrityError:
        await db.rollback()  # course entre deux ouvertures simultanées : déjà comptée
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.warning("Enregistrement de vue échoué (job=%s): %s", job_id, exc)


# ---------- « Mon entreprise » (profil recruteur) ----------
class CompanyProfile(BaseModel):
    company_name: Optional[str] = None
    contact_phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None            # e-mail du compte (lecture seule)
    whatsapp: Optional[str] = None         # numéro normalisé, format wa.me (lecture seule)


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, max_length=120)
    contact_phone: Optional[str] = Field(default=None, max_length=40)
    website: Optional[str] = Field(default=None, max_length=200)


def _company_out(prof: Optional[Recruiter_profiles], email: Optional[str]) -> CompanyProfile:
    from services.notifications import _normalize_phone

    phone = (prof.contact_phone or "") if prof else ""
    return CompanyProfile(
        company_name=prof.company_name if prof else None,
        contact_phone=phone or None,
        website=prof.website if prof else None,
        email=email,
        whatsapp=_normalize_phone(phone).lstrip("+") or None,
    )


@router.get("/company", response_model=CompanyProfile)
async def get_company(
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    prof = (await db.execute(
        select(Recruiter_profiles).where(Recruiter_profiles.user_id == str(recruiter.id))
    )).scalars().first()
    return _company_out(prof, recruiter.email)


@router.put("/company", response_model=CompanyProfile)
async def update_company(
    data: CompanyUpdate,
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour le profil entreprise. Le numéro WhatsApp sert immédiatement au bouton
    « Postuler via WhatsApp » de TOUTES les offres du recruteur (lu à la volée)."""
    from services.notifications import _normalize_phone

    fields = data.model_dump(exclude_unset=True)
    if "company_name" in fields and not (fields["company_name"] or "").strip():
        raise HTTPException(status_code=400, detail="Le nom de l'entreprise est requis.")
    if fields.get("contact_phone"):
        digits = re.sub(r"\D", "", _normalize_phone(fields["contact_phone"]))
        if not 8 <= len(digits) <= 15:
            raise HTTPException(status_code=400, detail="Numéro WhatsApp invalide (indicatif + numéro, ex. +225 07 00 00 00 00).")
    website = (fields.get("website") or "").strip()
    if website and not re.match(r"^https?://", website):
        fields["website"] = "https://" + website

    prof = (await db.execute(
        select(Recruiter_profiles).where(Recruiter_profiles.user_id == str(recruiter.id))
    )).scalars().first()
    if not prof:
        prof = Recruiter_profiles(user_id=str(recruiter.id))
        db.add(prof)
    for key, value in fields.items():
        setattr(prof, key, (value or "").strip() or None)
    await db.commit()
    await db.refresh(prof)
    return _company_out(prof, recruiter.email)


# ---------- Statistiques recruteur ----------
class JobStats(BaseModel):
    job_id: int
    title: str
    status: str
    views: int = 0            # vues uniques (appli + page publique)
    views_7d: int = 0
    applicants: int = 0
    saves: int = 0


class RecruiterStats(BaseModel):
    views: int = 0
    views_7d: int = 0
    applicants: int = 0
    saves: int = 0
    offers_online: int = 0
    jobs: List[JobStats] = []


@router.get("/stats", response_model=RecruiterStats)
async def recruiter_stats(
    recruiter: UserResponse = Depends(get_recruiter_user),
    db: AsyncSession = Depends(get_db),
):
    """Vues, candidatures et sauvegardes par offre du recruteur.

    Vues = ouvertures de la fiche dans l'appli (1 par candidat et par jour) + visites
    humaines uniques de la page publique `/offres/{id}` (analytics, robots exclus)."""
    postings = (await db.execute(
        select(Job_postings).where(Job_postings.posted_by == str(recruiter.id))
        .order_by(Job_postings.id.desc())
    )).scalars().all()
    if not postings:
        return RecruiterStats()
    ids = [p.job_id for p in postings]
    since = datetime.now() - timedelta(days=7)

    titles = {j.id: j.title for j in (await db.execute(
        select(Job_offers).where(Job_offers.id.in_(ids))
    )).scalars().all()}

    views: Dict[int, int] = {}
    views_7d: Dict[int, int] = {}
    for jid, created in (await db.execute(
        select(Job_views.job_id, Job_views.created_at).where(Job_views.job_id.in_(ids))
    )).all():
        views[jid] = views.get(jid, 0) + 1
        if created and created.replace(tzinfo=None) >= since:
            views_7d[jid] = views_7d.get(jid, 0) + 1

    # Pages publiques : un visiteur unique par jour (visitor_hash tourne chaque jour).
    path_to_id = {f"/offres/{i}": i for i in ids}
    seen = set()
    for path, vh, created in (await db.execute(
        select(PageView.path, PageView.visitor_hash, PageView.created_at).where(
            PageView.path.in_(list(path_to_id)), PageView.is_bot == False,  # noqa: E712
        )
    )).all():
        key = (path, vh or f"anon-{created}")
        if key in seen:
            continue
        seen.add(key)
        jid = path_to_id[path]
        views[jid] = views.get(jid, 0) + 1
        if created and created.replace(tzinfo=None) >= since:
            views_7d[jid] = views_7d.get(jid, 0) + 1

    applicants: Dict[int, int] = {}
    saves: Dict[int, int] = {}
    for u in (await db.execute(select(User_jobs).where(User_jobs.job_id.in_(ids)))).scalars().all():
        if (u.status or "").strip():
            applicants[u.job_id] = applicants.get(u.job_id, 0) + 1
        if u.saved:
            saves[u.job_id] = saves.get(u.job_id, 0) + 1

    rows = [JobStats(
        job_id=p.job_id, title=titles.get(p.job_id, "(offre supprimée)"), status=p.status,
        views=views.get(p.job_id, 0), views_7d=views_7d.get(p.job_id, 0),
        applicants=applicants.get(p.job_id, 0), saves=saves.get(p.job_id, 0),
    ) for p in postings]
    return RecruiterStats(
        views=sum(r.views for r in rows), views_7d=sum(r.views_7d for r in rows),
        applicants=sum(r.applicants for r in rows), saves=sum(r.saves for r in rows),
        offers_online=sum(1 for p in postings if p.status == "approved"),
        jobs=rows,
    )
