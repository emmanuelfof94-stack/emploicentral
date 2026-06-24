"""
API des organismes de formation partenaires.

- Côté candidat : annuaire des partenaires actifs + suggestions par thématique.
- Côté admin : CRUD complet (ajout/modification/suppression d'un organisme).

`pricing` vaut "free" (gratuit) ou "paid" (payant).
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
from models.training_partners import Training_partners
from schemas.auth import UserResponse
from services import training_partners as matching

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/training-partners", tags=["training-partners"])

_PRICING = {"free", "paid"}


# ---------- Schemas ----------
class PartnerResponse(BaseModel):
    id: int
    name: str
    url: str
    description: Optional[str] = None
    domains: Optional[str] = None
    pricing: str = "paid"
    logo_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PartnerCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    domains: Optional[str] = None
    pricing: str = "paid"
    logo_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location: Optional[str] = None
    is_active: bool = True


class PartnerUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    domains: Optional[str] = None
    pricing: Optional[str] = None
    logo_url: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


def _normalize_pricing(value: Optional[str], default: str = "paid") -> str:
    v = (value or "").strip().lower()
    return v if v in _PRICING else default


# ---------- Endpoints candidat ----------
@router.get("", response_model=List[PartnerResponse])
@router.get("/", response_model=List[PartnerResponse])
async def list_partners(
    pricing: Optional[str] = Query(None, description="Filtre 'free' ou 'paid'"),
    _user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Annuaire des organismes partenaires actifs (gratuits avant payants)."""
    stmt = select(Training_partners).where(Training_partners.is_active == True)  # noqa: E712
    if pricing and pricing.lower() in _PRICING:
        stmt = stmt.where(Training_partners.pricing == pricing.lower())
    rows = (await db.execute(stmt)).scalars().all()
    # Gratuits d'abord, puis par nom — annuaire lisible et stable.
    rows = sorted(
        rows,
        key=lambda p: (0 if (p.pricing or "").lower() == "free" else 1, (p.name or "").lower()),
    )
    return rows


@router.get("/suggest", response_model=List[PartnerResponse])
async def suggest_partners(
    theme: str = Query(..., description="Thématique de formation à faire correspondre"),
    limit: int = Query(6, ge=1, le=20),
    _user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Partenaires recommandés pour une thématique (pertinents, gratuits d'abord)."""
    rows = (await db.execute(
        select(Training_partners).where(Training_partners.is_active == True)  # noqa: E712
    )).scalars().all()
    ranked = matching.rank_partners(list(rows), theme)
    return ranked[:limit]


# ---------- Endpoints admin ----------
@router.get("/admin/all", response_model=List[PartnerResponse])
async def admin_all_partners(
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Training_partners).order_by(Training_partners.id.desc())
    )).scalars().all()
    return rows


@router.post("/admin", response_model=PartnerResponse, status_code=201)
async def create_partner(
    data: PartnerCreate,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    name = (data.name or "").strip()
    url = (data.url or "").strip()
    if not name or not url:
        raise HTTPException(status_code=400, detail="Le nom et l'URL sont requis.")
    partner = Training_partners(
        name=name,
        url=url,
        description=(data.description or "").strip() or None,
        domains=(data.domains or "").strip() or None,
        pricing=_normalize_pricing(data.pricing),
        logo_url=(data.logo_url or "").strip() or None,
        contact_email=(data.contact_email or "").strip() or None,
        contact_phone=(data.contact_phone or "").strip() or None,
        location=(data.location or "").strip() or None,
        is_active=bool(data.is_active),
    )
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return partner


@router.put("/admin/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: int,
    data: PartnerUpdate,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    partner = (await db.execute(
        select(Training_partners).where(Training_partners.id == partner_id)
    )).scalars().first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partenaire introuvable.")

    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        if key == "pricing":
            partner.pricing = _normalize_pricing(value, partner.pricing)
        elif key in ("name", "url", "description", "domains", "logo_url",
                     "contact_email", "contact_phone", "location"):
            v = (value or "").strip() if isinstance(value, str) else value
            setattr(partner, key, v or None)
        elif key == "is_active":
            partner.is_active = bool(value)

    if not partner.name or not partner.url:
        raise HTTPException(status_code=400, detail="Le nom et l'URL sont requis.")

    await db.commit()
    await db.refresh(partner)
    return partner


@router.delete("/admin/{partner_id}")
async def delete_partner(
    partner_id: int,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    partner = (await db.execute(
        select(Training_partners).where(Training_partners.id == partner_id)
    )).scalars().first()
    if not partner:
        raise HTTPException(status_code=404, detail="Partenaire introuvable.")
    await db.delete(partner)
    await db.commit()
    return {"success": True}
