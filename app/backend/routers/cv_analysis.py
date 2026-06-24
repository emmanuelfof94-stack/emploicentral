"""
CV Analysis API router.
Provides endpoints for CV analysis, compatibility scoring, and batch scoring.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.job_offers import Job_offers
from models.user_profiles import User_profiles
from schemas.auth import UserResponse
from services.cv_analysis import CvAnalysisService
from services.cv_generator import CvGeneratorService, build_pdf, build_cover_letter_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["cv_analysis"])


# ---------- Pydantic Schemas ----------
class AnalyzeCvRequest(BaseModel):
    """Request body for CV analysis."""
    pdf: str  # base64 data URI


class AnalyzeCvResponse(BaseModel):
    """Response for CV analysis."""
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[int] = None
    education: Optional[str] = None
    sector: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    profile_summary: Optional[str] = None


class CompatibilityScoreRequest(BaseModel):
    """Request body for single compatibility score."""
    profile_id: int
    job_id: int


class CompatibilityScoreResponse(BaseModel):
    """Response for compatibility score."""
    score: int
    strengths: List[str]
    gaps: List[str]
    summary: str
    job_id: int
    job_title: str
    company: str


class BatchScoresRequest(BaseModel):
    """Request body for batch scoring."""
    profile_id: int


class BatchScoreItem(BaseModel):
    """Single item in batch scores response."""
    job_id: Optional[int] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    score: int
    strengths: List[str]
    gaps: List[str]
    summary: str


class BatchScoresResponse(BaseModel):
    """Response for batch scoring."""
    scores: List[BatchScoreItem]
    total_jobs: int


class GenerateCvRequest(BaseModel):
    """Request body for ATS CV generation."""
    profile_id: int
    job_id: int
    template: Optional[str] = "sobre"  # sobre | bleu | compact


class GenerateCoverLetterRequest(BaseModel):
    """Request body for cover letter generation."""
    profile_id: int
    job_id: int
    template: Optional[str] = "sobre"


def _ascii_filename(text: str) -> str:
    """Nom de fichier ASCII sûr pour l'en-tête Content-Disposition."""
    import re as _re
    import unicodedata

    norm = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    norm = _re.sub(r"[^A-Za-z0-9._-]+", "_", norm).strip("_")
    return norm or "CV"


# ---------- Routes ----------
@router.post("/analyze-cv", response_model=AnalyzeCvResponse)
async def analyze_cv(
    data: AnalyzeCvRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a CV PDF and extract structured profile data.
    The PDF should be provided as a base64 data URI.
    """
    if not data.pdf:
        raise HTTPException(status_code=400, detail="PDF data is required.")

    # No DB work needed before AI call, just release any implicit transaction
    await db.rollback()

    service = CvAnalysisService()
    try:
        result = await service.analyze_cv(data.pdf)
        return AnalyzeCvResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"CV analysis failed: {str(e)}")


@router.post("/compatibility-score", response_model=CompatibilityScoreResponse)
async def compatibility_score(
    data: CompatibilityScoreRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate compatibility score between a user profile and a specific job.
    """
    # Phase 1: Fetch profile and job from DB
    profile_result = await db.execute(
        select(User_profiles).where(
            User_profiles.id == data.profile_id,
            User_profiles.user_id == str(current_user.id),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    job_result = await db.execute(
        select(Job_offers).where(Job_offers.id == data.job_id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job offer not found.")

    # Convert ORM objects to dicts
    profile_data = {
        "skills": profile.skills,
        "experience_years": profile.experience_years,
        "education": profile.education,
        "sector": profile.sector,
        "job_title": profile.job_title,
        "location": profile.location,
    }
    job_data = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "sector": job.sector,
        "requirements": job.requirements,
        "description": job.description,
        "location": job.location,
        "contract_type": job.contract_type,
    }

    # Capture identifiers before ending the transaction — after rollback the ORM
    # objects are expired and attribute access would trigger sync IO (greenlet error).
    job_id = job.id
    job_title = job.title
    job_company = job.company

    # End DB transaction before slow AI call
    await db.rollback()

    # Phase 2: AI scoring
    service = CvAnalysisService()
    try:
        result = await service.calculate_compatibility(profile_data, job_data)
        return CompatibilityScoreResponse(
            score=result["score"],
            strengths=result["strengths"],
            gaps=result["gaps"],
            summary=result["summary"],
            job_id=job_id,
            job_title=job_title,
            company=job_company,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compatibility scoring error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.post("/batch-scores", response_model=BatchScoresResponse)
async def batch_scores(
    data: BatchScoresRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate compatibility scores for a profile against all active job offers.
    Returns sorted list by score descending.
    """
    # Phase 1: Fetch profile and all active jobs
    profile_result = await db.execute(
        select(User_profiles).where(
            User_profiles.id == data.profile_id,
            User_profiles.user_id == str(current_user.id),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")

    jobs_result = await db.execute(
        select(Job_offers).where(Job_offers.is_active == True)
    )
    jobs = jobs_result.scalars().all()

    if not jobs:
        return BatchScoresResponse(scores=[], total_jobs=0)

    # Convert ORM objects to dicts
    profile_data = {
        "skills": profile.skills,
        "experience_years": profile.experience_years,
        "education": profile.education,
        "sector": profile.sector,
        "job_title": profile.job_title,
        "location": profile.location,
    }
    jobs_data = [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "sector": job.sector,
            "requirements": job.requirements,
            "description": job.description,
            "location": job.location,
            "contract_type": job.contract_type,
        }
        for job in jobs
    ]

    # End DB transaction before slow AI calls
    await db.rollback()

    # Phase 2: AI batch scoring
    service = CvAnalysisService()
    try:
        results = await service.batch_calculate_scores(profile_data, jobs_data)
        score_items = [BatchScoreItem(**item) for item in results]
        return BatchScoresResponse(scores=score_items, total_jobs=len(jobs_data))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch scoring error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch scoring failed: {str(e)}")


@router.get("/generate-cv")
async def generate_cv_get(
    profile_id: int,
    job_id: int,
    template: Optional[str] = "sobre",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Variante GET (navigation directe) — voir `generate_cv`. Permet le téléchargement
    sur Android, qui refuse les blob: et exige une vraie URL https."""
    return await generate_cv(
        GenerateCvRequest(profile_id=profile_id, job_id=job_id, template=template),
        current_user,
        db,
    )


@router.post("/generate-cv")
async def generate_cv(
    data: GenerateCvRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère un CV optimisé ATS adapté à une offre, à partir du profil du candidat.
    Renvoie un PDF téléchargeable.
    """
    # Phase 1: profil (avec contrôle d'appartenance) + offre
    profile_result = await db.execute(
        select(User_profiles).where(
            User_profiles.id == data.profile_id,
            User_profiles.user_id == str(current_user.id),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable.")

    job_result = await db.execute(select(Job_offers).where(Job_offers.id == data.job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable.")

    profile_data = {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "skills": profile.skills,
        "experience_years": profile.experience_years,
        "education": profile.education,
        "sector": profile.sector,
        "job_title": profile.job_title,
        "location": profile.location,
        "profile_summary": profile.profile_summary,
        "cv_object_key": profile.cv_object_key,
    }
    job_data = {
        "title": job.title,
        "company": job.company,
        "sector": job.sector,
        "requirements": job.requirements,
        "description": job.description,
        "location": job.location,
    }
    job_title = job.title or "offre"

    # Fin de transaction avant un éventuel appel IA lent.
    await db.rollback()

    # Phase 2: génération (IA si dispo, sinon locale) + rendu PDF
    service = CvGeneratorService()
    try:
        content = await service.generate(profile_data, job_data)
        pdf_bytes = build_pdf(content, template=data.template)
    except Exception as e:
        logger.error(f"CV generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Génération du CV échouée: {str(e)}")

    filename = "CV_%s_%s.pdf" % (
        _ascii_filename(content.get("full_name", "candidat")),
        _ascii_filename(job_title)[:40],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/generate-cover-letter")
async def generate_cover_letter_get(
    profile_id: int,
    job_id: int,
    template: Optional[str] = "sobre",
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Variante GET (navigation directe) — voir `generate_cover_letter`. Permet le
    téléchargement sur Android, qui refuse les blob: et exige une vraie URL https."""
    return await generate_cover_letter(
        GenerateCoverLetterRequest(profile_id=profile_id, job_id=job_id, template=template),
        current_user,
        db,
    )


@router.post("/generate-cover-letter")
async def generate_cover_letter(
    data: GenerateCoverLetterRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Génère une lettre de motivation adaptée à une offre, à partir du profil du candidat.
    Renvoie un PDF téléchargeable.
    """
    profile_result = await db.execute(
        select(User_profiles).where(
            User_profiles.id == data.profile_id,
            User_profiles.user_id == str(current_user.id),
        )
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profil introuvable.")

    job_result = await db.execute(select(Job_offers).where(Job_offers.id == data.job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Offre introuvable.")

    profile_data = {
        "full_name": profile.full_name,
        "email": profile.email,
        "phone": profile.phone,
        "skills": profile.skills,
        "experience_years": profile.experience_years,
        "education": profile.education,
        "sector": profile.sector,
        "job_title": profile.job_title,
        "location": profile.location,
    }
    job_data = {
        "title": job.title,
        "company": job.company,
        "sector": job.sector,
        "requirements": job.requirements,
        "description": job.description,
    }
    job_title = job.title or "offre"

    from datetime import datetime as _dt
    date_str = _dt.now().strftime("%d/%m/%Y")

    await db.rollback()

    service = CvGeneratorService()
    try:
        content = await service.generate_cover_letter(profile_data, job_data, date_str=date_str)
        pdf_bytes = build_cover_letter_pdf(content, template=data.template)
    except Exception as e:
        logger.error(f"Cover letter generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Génération de la lettre échouée: {str(e)}")

    filename = "Lettre_%s_%s.pdf" % (
        _ascii_filename(content.get("full_name", "candidat")),
        _ascii_filename(job_title)[:40],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )