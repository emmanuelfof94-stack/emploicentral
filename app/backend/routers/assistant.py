"""Assistant de recherche d'emploi en conversation (voir services/job_assistant.py)."""
from __future__ import annotations

import logging
from datetime import date
from typing import Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.job_offers import Job_offers
from models.job_postings import Job_postings
from models.user_profiles import User_profiles
from routers.public_jobs import _live_filter
from schemas.auth import UserResponse
from services import job_assistant as assistant
from services.interview_coach import ai_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

# Plafond de messages par candidat et par jour (coût IA + abus), en mémoire du processus.
DAILY_MESSAGE_LIMIT = 40
_usage: Dict[str, Tuple[str, int]] = {}


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: List[ChatTurn] = Field(min_length=1, max_length=20)


class SuggestedJob(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str] = None
    contract_type: Optional[str] = None
    sector: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    jobs: List[SuggestedJob]
    ai: bool
    remaining_today: int


def _consume_quota(user_id: str) -> int:
    today = date.today().isoformat()
    day, count = _usage.get(user_id, (today, 0))
    if day != today:
        count = 0
    if count >= DAILY_MESSAGE_LIMIT:
        raise HTTPException(status_code=429, detail="Vous avez atteint la limite de messages pour aujourd'hui. "
                                                    "Revenez demain !")
    _usage[user_id] = (today, count + 1)
    return DAILY_MESSAGE_LIMIT - count - 1


async def _load_jobs(db: AsyncSession) -> List[assistant.JobRow]:
    unapproved = select(Job_postings.job_id).where(Job_postings.status != "approved")
    recency = func.coalesce(Job_offers.posted_date, func.substr(cast(Job_offers.created_at, String), 1, 10))
    stmt = _live_filter(select(
        Job_offers.id, Job_offers.title, Job_offers.company, Job_offers.location, Job_offers.contract_type,
        Job_offers.sector, func.substr(Job_offers.description, 1, 800), recency,
    )).where(Job_offers.id.notin_(unapproved))
    rows = (await db.execute(stmt)).all()
    return [assistant.JobRow(id=r[0], title=r[1] or "", company=r[2] or "", location=r[3], contract_type=r[4],
                             sector=r[5], description=r[6] or "", recency=r[7] or "") for r in rows]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Le dernier message doit venir du candidat.")
    remaining = _consume_quota(str(current_user.id))

    fields = ("job_title", "sector", "experience_years", "education", "skills")
    # Seulement les champs utiles (pas le texte intégral du CV).
    prof = (await db.execute(
        select(*(getattr(User_profiles, f) for f in fields)).where(User_profiles.user_id == str(current_user.id))
    )).first()
    profile = dict(zip(fields, prof)) if prof else None
    skills = [s.strip() for s in (profile.get("skills") or "").split(",")] if profile else []

    history = [m.model_dump() for m in data.messages]
    # Recherche sur les derniers messages du candidat : « et en CDD ? » garde le métier demandé avant.
    recent_user_text = " ".join([m["content"] for m in history if m["role"] == "user"][-3:])
    query = assistant.parse_query(recent_user_text)
    jobs = await assistant.rank_in_thread(await _load_jobs(db), query, skills)

    used_ai = False
    reply = None
    if ai_available():
        try:
            reply = await assistant.ai_reply(history, profile, jobs)
            used_ai = True
        except Exception as exc:  # noqa: BLE001 — repli local, jamais d'erreur côté candidat
            logger.warning("Assistant: IA indisponible, repli local : %s", exc)
    if reply is None:
        reply = assistant.local_reply(query, jobs)

    ids = assistant.cited_ids(reply, jobs)
    by_id = {j.id: j for j in jobs}
    shown = [by_id[i] for i in ids] or (list(jobs[:5]) if not used_ai else [])
    return ChatResponse(
        reply=reply,
        jobs=[SuggestedJob(id=j.id, title=j.title, company=j.company, location=j.location,
                           contract_type=j.contract_type, sector=j.sector) for j in shown],
        ai=used_ai,
        remaining_today=remaining,
    )
