"""
Tendances du marché de l'emploi (Côte d'Ivoire & Afrique de l'Ouest).

Agrège les offres ACTIVES pour répondre à : quels domaines recrutent le plus ?
quelles compétences sont les plus demandées ? quelles villes recrutent ?
Tout est calculé à la volée à partir de `job_offers` (champ `sector` pour les
domaines, `requirements`/`description`/`title` pour les compétences via le même
moteur que le matching CV — `extract_job_keywords`).
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.job_offers import Job_offers
from schemas.auth import UserResponse
from services.cv_generator import extract_job_keywords

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/market", tags=["market"])


class CountItem(BaseModel):
    name: str
    count: int


class MarketInsights(BaseModel):
    total_active: int
    top_sectors: List[CountItem]
    top_skills: List[CountItem]
    top_locations: List[CountItem]


def _city(location: Optional[str]) -> Optional[str]:
    """Garde la ville (avant la 1re virgule) pour regrouper proprement."""
    if not location:
        return None
    return location.split(",")[0].strip() or None


@router.get("/insights", response_model=MarketInsights)
async def market_insights(
    top: int = Query(10, ge=1, le=30),
    _user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Job_offers))).scalars().all()

    today = date.today().isoformat()
    # Offres actives = non désactivées et non expirées.
    active = [
        j for j in rows
        if j.is_active is not False and (not j.valid_through or j.valid_through >= today)
    ]

    sectors: Counter = Counter()
    skills: Counter = Counter()
    locations: Counter = Counter()

    for j in active:
        if (j.sector or "").strip():
            sectors[j.sector.strip()] += 1
        c = _city(j.location)
        if c:
            locations[c] += 1
        # Compétences saillantes de l'offre (titre + exigences + description + secteur).
        for kw in extract_job_keywords({
            "title": j.title, "requirements": j.requirements,
            "description": j.description, "sector": j.sector,
        }):
            skills[kw] += 1

    def to_items(counter: Counter) -> List[CountItem]:
        return [CountItem(name=n, count=c) for n, c in counter.most_common(top)]

    return MarketInsights(
        total_active=len(active),
        top_sectors=to_items(sectors),
        top_skills=to_items(skills),
        top_locations=to_items(locations),
    )
