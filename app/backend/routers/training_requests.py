"""
API des demandes de formation (parcours généré par IA).

- Le candidat soumet une thématique → un parcours est généré (IA si configurée,
  sinon moteur local) et stocké, scopé par utilisateur.
- L'équipe (admins) est notifiée de chaque nouvelle demande (in-app + email).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_admin_user, get_current_user
from models.auth import User
from models.notifications import Notification
from models.training_requests import Training_requests
from models.user_profiles import User_profiles
from schemas.auth import UserResponse
from services import training_generator, training_quota
from services.notifications import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trainings", tags=["trainings"])


# ---------- Schemas ----------
class GenerateTrainingRequest(BaseModel):
    theme: str
    level: Optional[str] = None
    objective: Optional[str] = None


class TrainingResponse(BaseModel):
    id: int
    theme: str
    level: Optional[str] = None
    objective: Optional[str] = None
    program: Optional[str] = None
    ai_generated: Optional[bool] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminTrainingResponse(TrainingResponse):
    user_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None


class ThemesResponse(BaseModel):
    themes: List[str]
    levels: List[str]


# ---------- Notification admin ----------
async def _notify_admins(db: AsyncSession, req: Training_requests, candidate: UserResponse, candidate_name: str) -> None:
    """Crée une notif in-app + envoie un email à chaque admin (best-effort)."""
    try:
        admins = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
        if not admins:
            return
        who = candidate_name or candidate.email or "Un candidat"
        title = f"🎓 Nouvelle demande de formation : {req.theme}"
        body = f"{who} souhaite se former sur « {req.theme} »"
        if req.level:
            body += f" (niveau {req.level})"
        for admin in admins:
            db.add(Notification(
                user_id=admin.id, job_id=None, title=title, body=body,
                channels="in_app,email", is_read=False,
            ))
        await db.commit()

        # Emails après commit (n'impacte pas l'enregistrement in-app).
        html = (
            f"<h2>{title}</h2>"
            f"<p><b>Candidat :</b> {who}"
            + (f" ({candidate.email})" if candidate.email else "")
            + "</p>"
            f"<p><b>Thématique :</b> {req.theme}</p>"
            + (f"<p><b>Niveau :</b> {req.level}</p>" if req.level else "")
            + (f"<p><b>Objectif :</b> {req.objective}</p>" if req.objective else "")
            + "<hr><p style='color:#888;font-size:12px'>EmploiCentral — demande de formation</p>"
        )
        for admin in admins:
            if admin.email:
                await send_email(admin.email, title, html)
    except Exception as exc:  # noqa: BLE001 - la notif ne doit jamais bloquer la demande
        logger.warning("Notification admin (formation) échouée: %s", exc)


# ---------- Endpoints ----------
@router.get("/themes", response_model=ThemesResponse)
async def list_themes(_user: UserResponse = Depends(get_current_user)):
    return ThemesResponse(
        themes=training_generator.SUGGESTED_THEMES,
        levels=training_generator.LEVELS,
    )


@router.get("/mine", response_model=List[TrainingResponse])
async def my_trainings(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Training_requests)
        .where(Training_requests.user_id == str(current_user.id))
        .order_by(Training_requests.id.desc())
    )).scalars().all()
    return rows


@router.post("/generate", response_model=TrainingResponse, status_code=201)
async def generate_training(
    data: GenerateTrainingRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    theme = (data.theme or "").strip()
    if not theme:
        raise HTTPException(status_code=400, detail="La thématique est requise.")

    # Quota : chaque génération consomme 1 accès. On bloque AVANT la génération
    # (coûteuse) si le candidat a épuisé ses accès gratuits sans avoir l'illimité.
    if not await training_quota.has_remaining(db, str(current_user.id)):
        await training_quota.notify_quota_blocked(db, str(current_user.id))
        raise training_quota.quota_exhausted_error()

    # Contexte profil (facultatif) pour personnaliser le parcours.
    profile = (await db.execute(
        select(User_profiles).where(User_profiles.user_id == str(current_user.id))
    )).scalars().first()
    profile_summary = (profile.profile_summary if profile else "") or ""
    candidate_name = (profile.full_name if profile else "") or current_user.name or ""

    result = await training_generator.generate_program(
        theme=theme,
        level=(data.level or "").strip(),
        objective=(data.objective or "").strip(),
        profile_summary=profile_summary,
    )

    req = Training_requests(
        user_id=str(current_user.id),
        theme=theme,
        level=(data.level or "").strip() or None,
        objective=(data.objective or "").strip() or None,
        program=result["program"],
        ai_generated=bool(result["ai_generated"]),
        status="generated",
    )
    db.add(req)
    await db.flush()  # obtient req.id pour référencer l'accès consommé
    # Consomme l'accès dans la même transaction que la création du parcours :
    # une génération échouée ne débite jamais le quota.
    await training_quota.consume(db, str(current_user.id), "generate", str(req.id), commit=False)
    await db.commit()
    await db.refresh(req)

    await _notify_admins(db, req, current_user, candidate_name)
    return req


@router.delete("/{training_id}")
async def delete_training(
    training_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(
        select(Training_requests).where(
            Training_requests.id == training_id,
            Training_requests.user_id == str(current_user.id),
        )
    )).scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    await db.delete(row)
    await db.commit()
    return {"success": True}


@router.get("/admin/all", response_model=List[AdminTrainingResponse])
async def admin_all_trainings(
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Training_requests).order_by(Training_requests.id.desc()).offset(skip).limit(limit)
    )).scalars().all()

    # Résout nom/email candidat (map user_id -> profil) en une requête.
    user_ids = list({r.user_id for r in rows})
    profiles = {}
    if user_ids:
        prof_rows = (await db.execute(
            select(User_profiles).where(User_profiles.user_id.in_(user_ids))
        )).scalars().all()
        profiles = {p.user_id: p for p in prof_rows}

    out: List[AdminTrainingResponse] = []
    for r in rows:
        p = profiles.get(r.user_id)
        out.append(AdminTrainingResponse(
            id=r.id, theme=r.theme, level=r.level, objective=r.objective,
            program=r.program, ai_generated=r.ai_generated, status=r.status,
            created_at=r.created_at, user_id=r.user_id,
            candidate_name=(p.full_name if p else None),
            candidate_email=(p.email if p else None),
        ))
    return out
