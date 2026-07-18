"""
API du catalogue de formations concrètes.

- Côté candidat : parcourir le catalogue (filtres domaine / gratuit) + suggestions
  de formations réelles pour une thématique.
- Côté admin : CRUD complet.

Distinct des parcours générés par IA (`/api/v1/trainings`) : ici ce sont de vraies
formations rattachées à un organisme partenaire.
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
from models.training_access import Training_access_events
from models.training_courses import Training_courses
from models.training_partners import Training_partners
from schemas.auth import UserResponse
from services import training_quota
from services.training_partners import relevance_score
from sqlalchemy import and_

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/training-courses", tags=["training-courses"])


# ---------- Schemas ----------
class CourseResponse(BaseModel):
    id: int
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    domain: Optional[str] = None
    level: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[str] = None
    is_free: Optional[bool] = None
    format: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    # Gratuites : l'URL n'est révélée qu'après déblocage (consomme 1 accès).
    # None pour les formations payantes (non concernées par le quota).
    is_unlocked: Optional[bool] = None

    class Config:
        from_attributes = True


class UnlockResponse(BaseModel):
    course_id: int
    url: Optional[str] = None
    unlocked: bool


class CourseCreate(BaseModel):
    title: str
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    level: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[str] = None
    is_free: bool = False
    format: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    is_active: bool = True


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    level: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[str] = None
    is_free: Optional[bool] = None
    format: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None


_STR_FIELDS = (
    "title", "partner_name", "description", "domain", "level",
    "duration", "price", "format", "location", "url",
)


def _sort_catalog(rows: List[Training_courses]) -> List[Training_courses]:
    """Gratuit d'abord, puis par domaine puis titre — catalogue lisible et stable."""
    return sorted(
        rows,
        key=lambda c: (
            0 if c.is_free else 1,
            (c.domain or "").lower(),
            (c.title or "").lower(),
        ),
    )


async def _unlocked_ids(db: AsyncSession, user_id: str) -> set[str]:
    """Ids (en str) des formations gratuites déjà débloquées par le candidat."""
    rows = (await db.execute(
        select(Training_access_events.ref).where(
            Training_access_events.user_id == user_id,
            Training_access_events.kind == "catalog",
        )
    )).scalars().all()
    return {r for r in rows if r}


async def _present(db: AsyncSession, user_id: str, rows: List[Training_courses]) -> List[CourseResponse]:
    """Sérialise les formations en masquant l'URL des gratuites non débloquées.

    - Gratuite non débloquée : `url=None`, `is_unlocked=False` (le front propose « Débloquer »).
    - Gratuite débloquée      : `url` révélée, `is_unlocked=True`.
    - Payante                 : `url` visible, `is_unlocked=None` (hors quota).
    """
    unlocked = await _unlocked_ids(db, user_id) if any(c.is_free for c in rows) else set()
    out: List[CourseResponse] = []
    for c in rows:
        item = CourseResponse.model_validate(c)
        if c.is_free:
            is_unlocked = str(c.id) in unlocked
            item.is_unlocked = is_unlocked
            if not is_unlocked:
                item.url = None
        out.append(item)
    return out


async def _resolve_partner_name(db: AsyncSession, partner_id: Optional[int], fallback: Optional[str]) -> Optional[str]:
    """Renseigne `partner_name` depuis le partenaire si un id est fourni."""
    if partner_id:
        partner = (await db.execute(
            select(Training_partners).where(Training_partners.id == partner_id)
        )).scalars().first()
        if partner:
            return partner.name
    return (fallback or "").strip() or None


# ---------- Endpoints candidat ----------
@router.get("", response_model=List[CourseResponse])
@router.get("/", response_model=List[CourseResponse])
async def list_courses(
    domain: Optional[str] = Query(None),
    is_free: Optional[bool] = Query(None),
    partner_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Recherche plein texte (titre/description/domaine)"),
    user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Catalogue des formations actives (gratuites d'abord)."""
    stmt = select(Training_courses).where(Training_courses.is_active == True)  # noqa: E712
    if domain:
        stmt = stmt.where(Training_courses.domain == domain)
    if is_free is not None:
        stmt = stmt.where(Training_courses.is_free == is_free)
    if partner_id:
        stmt = stmt.where(Training_courses.partner_id == partner_id)
    rows = list((await db.execute(stmt)).scalars().all())

    if q:
        needle = q.strip().lower()
        rows = [
            c for c in rows
            if needle in (c.title or "").lower()
            or needle in (c.description or "").lower()
            or needle in (c.domain or "").lower()
        ]
    return await _present(db, str(user.id), _sort_catalog(rows))


@router.get("/domains", response_model=List[str])
async def list_course_domains(
    _user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Domaines distincts présents dans le catalogue actif (pour les filtres)."""
    rows = (await db.execute(
        select(Training_courses.domain).where(Training_courses.is_active == True)  # noqa: E712
    )).scalars().all()
    domains = sorted({(d or "").strip() for d in rows if (d or "").strip()})
    return domains


@router.get("/suggest", response_model=List[CourseResponse])
async def suggest_courses(
    theme: str = Query(..., description="Thématique à faire correspondre"),
    limit: int = Query(4, ge=1, le=20),
    user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Formations réelles recommandées pour une thématique (pertinentes, gratuites d'abord)."""
    rows = list((await db.execute(
        select(Training_courses).where(Training_courses.is_active == True)  # noqa: E712
    )).scalars().all())

    def key(c: Training_courses):
        score = relevance_score(c.domain or "", c.title or "", theme)
        return (-score, 0 if c.is_free else 1, (c.title or "").lower())

    ranked = sorted(rows, key=key)
    # Ne garder que des formations avec une réelle correspondance.
    relevant = [c for c in ranked if relevance_score(c.domain or "", c.title or "", theme) > 0]
    return await _present(db, str(user.id), relevant[:limit])


@router.post("/{course_id}/unlock", response_model=UnlockResponse)
async def unlock_course(
    course_id: int,
    user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Débloque une formation gratuite (consomme 1 accès) et révèle son lien.

    Idempotent : rouvrir une formation déjà débloquée ne reconsomme pas d'accès.
    Quota épuisé sans accès illimité → 402 (le front affiche le paywall).
    """
    course = (await db.execute(
        select(Training_courses).where(
            and_(Training_courses.id == course_id, Training_courses.is_active == True)  # noqa: E712
        )
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    if not course.is_free:
        # Les formations payantes ne sont pas concernées par le quota : lien direct.
        return UnlockResponse(course_id=course_id, url=course.url, unlocked=True)

    uid = str(user.id)
    already = str(course_id) in await _unlocked_ids(db, uid)
    if not already and not await training_quota.has_remaining(db, uid):
        await training_quota.notify_quota_blocked(db, uid)
        raise training_quota.quota_exhausted_error()

    # consume() est idempotent sur (kind, ref) : pas de double débit.
    await training_quota.consume(db, uid, "catalog", str(course_id))
    return UnlockResponse(course_id=course_id, url=course.url, unlocked=True)


# ---------- Endpoints admin ----------
@router.get("/admin/all", response_model=List[CourseResponse])
async def admin_all_courses(
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Training_courses).order_by(Training_courses.id.desc())
    )).scalars().all()
    return rows


@router.post("/admin", response_model=CourseResponse, status_code=201)
async def create_course(
    data: CourseCreate,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    title = (data.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Le titre est requis.")
    partner_name = await _resolve_partner_name(db, data.partner_id, data.partner_name)
    course = Training_courses(
        partner_id=data.partner_id,
        partner_name=partner_name,
        title=title,
        description=(data.description or "").strip() or None,
        domain=(data.domain or "").strip() or None,
        level=(data.level or "").strip() or None,
        duration=(data.duration or "").strip() or None,
        price=(data.price or "").strip() or None,
        is_free=bool(data.is_free),
        format=(data.format or "").strip() or None,
        location=(data.location or "").strip() or None,
        url=(data.url or "").strip() or None,
        is_active=bool(data.is_active),
    )
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


@router.put("/admin/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    data: CourseUpdate,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    course = (await db.execute(
        select(Training_courses).where(Training_courses.id == course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Formation introuvable.")

    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        if key in _STR_FIELDS:
            v = (value or "").strip() if isinstance(value, str) else value
            setattr(course, key, v or None)
        elif key in ("is_free", "is_active"):
            setattr(course, key, bool(value))
        elif key == "partner_id":
            course.partner_id = value

    # Re-synchronise le nom du partenaire si l'id a changé.
    if "partner_id" in fields:
        course.partner_name = await _resolve_partner_name(db, course.partner_id, course.partner_name)

    if not (course.title or "").strip():
        raise HTTPException(status_code=400, detail="Le titre est requis.")

    await db.commit()
    await db.refresh(course)
    return course


@router.delete("/admin/{course_id}")
async def delete_course(
    course_id: int,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    course = (await db.execute(
        select(Training_courses).where(Training_courses.id == course_id)
    )).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    await db.delete(course)
    await db.commit()
    return {"success": True}
