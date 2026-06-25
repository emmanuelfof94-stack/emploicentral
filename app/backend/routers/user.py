import csv
import io
from datetime import datetime
from typing import List, Optional

from core.database import get_db
from dependencies.auth import get_admin_user, get_current_user
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from models.auth import User
from models.user_profiles import User_profiles
from pydantic import BaseModel
from schemas.auth import UserResponse
from services.user import UserService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None


class AdminUserRow(BaseModel):
    """Une personne inscrite, enrichie de quelques infos de profil (vue admin)."""
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    auth_type: str = "local"            # "local" (email/mot de passe) ou "platform" (OIDC)
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    sector: Optional[str] = None
    job_title: Optional[str] = None
    cv_analyzed: Optional[bool] = None


class AdminUsersResponse(BaseModel):
    total: int
    items: List[AdminUserRow]


@router.get("/admin/all", response_model=AdminUsersResponse)
async def admin_list_users(
    q: Optional[str] = Query(None, description="Recherche nom/email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste les comptes inscrits (admin), enrichis du profil, les plus récents d'abord."""
    total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0

    users = (await db.execute(
        select(User).order_by(User.created_at.desc().nullslast()).offset(skip).limit(limit)
    )).scalars().all()

    # Profils en une requête (map user_id -> profil) pour éviter le N+1.
    ids = [u.id for u in users]
    profiles = {}
    if ids:
        rows = (await db.execute(
            select(User_profiles).where(User_profiles.user_id.in_(ids))
        )).scalars().all()
        profiles = {p.user_id: p for p in rows}

    items: List[AdminUserRow] = []
    for u in users:
        p = profiles.get(u.id)
        # full_name du profil prioritaire sur le name du compte.
        display_name = (p.full_name if p and p.full_name else None) or u.name
        row = AdminUserRow(
            id=u.id,
            email=u.email or (p.email if p else None),
            name=display_name,
            role=u.role,
            auth_type="local" if u.password_hash else "platform",
            created_at=u.created_at,
            last_login=u.last_login,
            phone=(p.phone if p else None),
            location=(p.location if p else None),
            sector=(p.sector if p else None),
            job_title=(p.job_title if p else None),
            cv_analyzed=(p.cv_analyzed if p else None),
        )
        if q:
            needle = q.strip().lower()
            hay = " ".join(filter(None, [row.name, row.email])).lower()
            if needle not in hay:
                continue
        items.append(row)

    return AdminUsersResponse(total=total, items=items)


@router.get("/admin/export")
async def admin_export_users(
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Export CSV de tous les comptes inscrits (enrichis du profil)."""
    users = (await db.execute(
        select(User).order_by(User.created_at.desc().nullslast())
    )).scalars().all()

    ids = [u.id for u in users]
    profiles = {}
    if ids:
        rows = (await db.execute(
            select(User_profiles).where(User_profiles.user_id.in_(ids))
        )).scalars().all()
        profiles = {p.user_id: p for p in rows}

    buf = io.StringIO()
    buf.write("﻿")  # BOM UTF-8 → accents corrects à l'ouverture dans Excel
    # Séparateur ';' = compatible Excel en locale française.
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "Nom", "Email", "Rôle", "Type de compte", "Inscription",
        "Dernière connexion", "Téléphone", "Ville", "Secteur", "Métier", "CV analysé",
    ])

    def dt(value) -> str:
        return value.strftime("%Y-%m-%d %H:%M") if value else ""

    for u in users:
        p = profiles.get(u.id)
        name = (p.full_name if p and p.full_name else None) or u.name or ""
        writer.writerow([
            name,
            u.email or (p.email if p else "") or "",
            u.role or "",
            "Email/mot de passe" if u.password_hash else "Plateforme",
            dt(u.created_at),
            dt(u.last_login),
            (p.phone if p else "") or "",
            (p.location if p else "") or "",
            (p.sector if p else "") or "",
            (p.job_title if p else "") or "",
            "Oui" if (p and p.cv_analyzed) else "Non",
        ])

    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=inscrits_emploicentral.csv"},
    )


class AdminJobActivity(BaseModel):
    job_id: int
    title: Optional[str] = None
    company: Optional[str] = None
    saved: Optional[bool] = None
    status: Optional[str] = None
    updated_at: Optional[datetime] = None


class AdminTrainingActivity(BaseModel):
    id: int
    theme: str
    level: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminUserActivity(BaseModel):
    user: AdminUserRow
    counts: dict
    saved_jobs: List[AdminJobActivity]
    applications: List[AdminJobActivity]
    trainings: List[AdminTrainingActivity]


@router.get("/admin/{user_id}/activity", response_model=AdminUserActivity)
async def admin_user_activity(
    user_id: str,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Détaille ce qu'a fait une personne : offres sauvegardées, candidatures, formations."""
    # Imports locaux pour ne pas alourdir le chargement du module.
    from models.job_offers import Job_offers
    from models.notifications import Notification
    from models.training_requests import Training_requests
    from models.user_jobs import User_jobs

    user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    profile = (await db.execute(
        select(User_profiles).where(User_profiles.user_id == user_id)
    )).scalars().first()

    user_row = AdminUserRow(
        id=user.id,
        email=user.email or (profile.email if profile else None),
        name=(profile.full_name if profile and profile.full_name else None) or user.name,
        role=user.role,
        auth_type="local" if user.password_hash else "platform",
        created_at=user.created_at,
        last_login=user.last_login,
        phone=(profile.phone if profile else None),
        location=(profile.location if profile else None),
        sector=(profile.sector if profile else None),
        job_title=(profile.job_title if profile else None),
        cv_analyzed=(profile.cv_analyzed if profile else None),
    )

    # Interactions offres (sauvegardes + candidatures), enrichies du titre de l'offre.
    uj = (await db.execute(
        select(User_jobs)
        .where(User_jobs.user_id == user_id)
        .order_by(User_jobs.updated_at.desc().nullslast())
    )).scalars().all()

    job_ids = list({r.job_id for r in uj})
    jobs_map = {}
    if job_ids:
        jrows = (await db.execute(
            select(Job_offers).where(Job_offers.id.in_(job_ids))
        )).scalars().all()
        jobs_map = {j.id: j for j in jrows}

    def to_item(r) -> AdminJobActivity:
        j = jobs_map.get(r.job_id)
        return AdminJobActivity(
            job_id=r.job_id,
            title=(j.title if j else None),
            company=(j.company if j else None),
            saved=r.saved,
            status=r.status,
            updated_at=r.updated_at,
        )

    saved_jobs = [to_item(r) for r in uj if r.saved]
    applications = [to_item(r) for r in uj if (r.status or "").strip()]

    trainings = (await db.execute(
        select(Training_requests).where(Training_requests.user_id == user_id)
        .order_by(Training_requests.id.desc())
    )).scalars().all()
    training_items = [
        AdminTrainingActivity(id=t.id, theme=t.theme, level=t.level, status=t.status, created_at=t.created_at)
        for t in trainings
    ]

    notif_count = (await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )).scalar() or 0

    counts = {
        "saved_jobs": len(saved_jobs),
        "applications": len(applications),
        "trainings": len(training_items),
        "notifications": int(notif_count),
        "cv_analyzed": bool(user_row.cv_analyzed),
    }

    return AdminUserActivity(
        user=user_row,
        counts=counts,
        saved_jobs=saved_jobs,
        applications=applications,
        trainings=training_items,
    )


@router.get("/profile", response_model=UserResponse)
async def get_profile(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    profile = await UserService.get_user_profile(db, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return profile


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current user profile"""
    profile = await UserService.update_user_profile(db, current_user.id, profile_data.name)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return profile
