"""Analytics intégré — collecte des vues de page + tableau de bord admin.

- POST /api/v1/analytics/track  : public, appelé par le front à chaque page vue.
- GET  /api/v1/analytics/stats  : admin, agrégats pour le tableau de bord.

Respect de la vie privée : pas d'IP stockée, hash visiteur anonyme à rotation
quotidienne (pas de cookie, pas de bannière RGPD nécessaire).
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

from core.config import settings
from core.database import get_db
from dependencies.auth import get_admin_user
from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from schemas.auth import UserResponse
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.analytics import PageView

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# User-agents à exclure des statistiques (bots, crawlers, monitoring…).
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bing|googlebot|baidu|yandex|duckduck|facebookexternalhit|"
    r"embedly|preview|monitor|curl|wget|python-requests|httpx|headless|lighthouse|"
    r"pingdom|uptimerobot|ahrefs|semrush|mj12|dotbot",
    re.I,
)


class TrackPayload(BaseModel):
    path: str
    referrer: Optional[str] = None


def _client_ip(request: Request) -> str:
    """IP réelle du client derrière le proxy (Fly / reverse proxy)."""
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _visitor_hash(ip: str, user_agent: str, day: str) -> str:
    """Hash anonyme et quotidien : identifie un visiteur sur la journée sans IP en clair."""
    salt = str(getattr(settings, "jwt_secret_key", "") or getattr(settings, "mask_key", "") or "salt")
    raw = f"{salt}|{day}|{ip}|{user_agent}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _referrer_host(referrer: Optional[str], own_host: str) -> str:
    """Réduit un référent à son host. Vide / propre domaine => "" (accès direct)."""
    if not referrer:
        return ""
    try:
        host = urlparse(referrer).netloc.lower()
    except Exception:
        return ""
    if not host or (own_host and host.endswith(own_host)):
        return ""
    return host[:100]


@router.post("/track", status_code=status.HTTP_204_NO_CONTENT)
async def track(payload: TrackPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Enregistre une vue de page. Ne lève jamais d'erreur visible côté visiteur."""
    try:
        path = (payload.path or "/").strip()[:300]
        if not path.startswith("/"):
            path = "/" + path

        ua = (request.headers.get("user-agent") or "")[:400]
        is_bot = bool(_BOT_RE.search(ua))
        own_host = urlparse(str(getattr(settings, "frontend_url", "") or "")).netloc.lower()

        ip = _client_ip(request)
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        view = PageView(
            path=path,
            referrer=_referrer_host(payload.referrer, own_host),
            visitor_hash=_visitor_hash(ip, ua, day),
            user_agent=ua,
            is_bot=is_bot,
        )
        db.add(view)
        await db.commit()
    except Exception as exc:  # pragma: no cover - l'analytics ne doit jamais casser l'UX
        logger.warning("analytics track failed: %s", type(exc).__name__)
    return None


@router.get("/stats")
async def stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _admin: UserResponse = Depends(get_admin_user),
):
    """Agrégats pour le tableau de bord (visites humaines uniquement)."""
    days = max(1, min(days, 365))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    human = PageView.is_bot == False  # noqa: E712  (SQL: is_bot = 0)

    # Totaux (tous temps)
    total_views = (await db.execute(select(func.count(PageView.id)).where(human))).scalar() or 0
    unique_visitors = (
        await db.execute(select(func.count(distinct(PageView.visitor_hash))).where(human))
    ).scalar() or 0

    # Aujourd'hui
    views_today = (
        await db.execute(select(func.count(PageView.id)).where(human, PageView.created_at >= start_today))
    ).scalar() or 0
    visitors_today = (
        await db.execute(
            select(func.count(distinct(PageView.visitor_hash))).where(human, PageView.created_at >= start_today)
        )
    ).scalar() or 0

    # Série par jour (N derniers jours)
    day_col = func.date(PageView.created_at)
    per_day_rows = (
        await db.execute(
            select(day_col.label("day"), func.count(PageView.id), func.count(distinct(PageView.visitor_hash)))
            .where(human, PageView.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
    ).all()
    per_day = [{"day": str(r[0]), "views": r[1], "visitors": r[2]} for r in per_day_rows]

    # Top pages
    top_pages_rows = (
        await db.execute(
            select(PageView.path, func.count(PageView.id).label("c"))
            .where(human, PageView.created_at >= since)
            .group_by(PageView.path)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
        )
    ).all()
    top_pages = [{"path": r[0], "views": r[1]} for r in top_pages_rows]

    # Top sources de trafic (référents). "" = accès direct.
    top_ref_rows = (
        await db.execute(
            select(PageView.referrer, func.count(PageView.id).label("c"))
            .where(human, PageView.created_at >= since)
            .group_by(PageView.referrer)
            .order_by(func.count(PageView.id).desc())
            .limit(10)
        )
    ).all()
    top_referrers = [
        {"source": (r[0] if r[0] else "Accès direct"), "views": r[1]} for r in top_ref_rows
    ]

    # Activité récente (flux en direct)
    recent_rows = (
        await db.execute(
            select(PageView.created_at, PageView.path, PageView.referrer)
            .where(human)
            .order_by(PageView.created_at.desc())
            .limit(20)
        )
    ).all()
    recent = [
        {
            "at": (r[0].isoformat() if r[0] else None),
            "path": r[1],
            "source": (r[2] if r[2] else "Accès direct"),
        }
        for r in recent_rows
    ]

    return {
        "range_days": days,
        "total_views": total_views,
        "unique_visitors": unique_visitors,
        "views_today": views_today,
        "visitors_today": visitors_today,
        "per_day": per_day,
        "top_pages": top_pages,
        "top_referrers": top_referrers,
        "recent": recent,
    }
