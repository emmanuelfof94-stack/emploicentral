"""In-app notifications API (liste + marquage lu)."""
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_admin_user, get_current_user
from models.notifications import Notification
from models.user_profiles import User_profiles
from schemas.auth import UserResponse
from services.notifications import list_whatsapp_templates, send_whatsapp_debug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationItem(BaseModel):
    id: int
    job_id: Optional[int] = None
    title: str
    body: Optional[str] = None
    channels: Optional[str] = None
    is_read: Optional[bool] = False
    created_at: Optional[str] = None


class NotificationsResponse(BaseModel):
    items: List[NotificationItem]
    unread: int


class MarkReadRequest(BaseModel):
    ids: Optional[List[int]] = None  # None => tout marquer lu


@router.get("", response_model=NotificationsResponse)
async def list_notifications(
    limit: int = 50,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Notification)
        .where(Notification.user_id == str(current_user.id))
        .order_by(Notification.id.desc())
        .limit(min(max(limit, 1), 200))
    )).scalars().all()
    items = [
        NotificationItem(
            id=r.id, job_id=r.job_id, title=r.title, body=r.body, channels=r.channels,
            is_read=bool(r.is_read),
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in rows
    ]
    unread = sum(1 for r in rows if not r.is_read)
    return NotificationsResponse(items=items, unread=unread)


@router.post("/mark-read")
async def mark_read(
    data: MarkReadRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = update(Notification).where(Notification.user_id == str(current_user.id))
    if data.ids:
        stmt = stmt.where(Notification.id.in_(data.ids))
    stmt = stmt.values(is_read=True)
    await db.execute(stmt)
    await db.commit()
    return {"ok": True}


@router.post("/admin/whatsapp-test")
async def whatsapp_test(
    admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Diagnostic admin : envoie le template WhatsApp sur le numéro du profil admin
    et renvoie le détail de la réponse Meta (statut + corps)."""
    prof = (await db.execute(
        select(User_profiles).where(User_profiles.user_id == str(admin.id))
    )).scalars().first()
    phone = ((prof.phone or "").strip() if prof else "")
    if not phone:
        return {"ok": False, "error": "Aucun numéro de téléphone dans le profil admin."}
    first = (prof.full_name or "").strip().split(" ")[0] if prof and prof.full_name else "Test"
    link = (os.environ.get("FRONTEND_URL") or "https://emploicentral.onrender.com").rstrip("/") + "/jobs"
    result = await send_whatsapp_debug(phone, params=[first or "Test", "1", link])
    # En cas d'échec, on liste les modèles réels pour un diagnostic immédiat.
    if not result.get("ok"):
        tpl = await list_whatsapp_templates()
        result["available_templates"] = tpl.get("templates")
        approved = [t for t in (tpl.get("templates") or []) if t.get("status") == "APPROVED"]
        if approved:
            result["hint"] = "Modèles approuvés : " + " | ".join(
                f"{t['name']} (langue={t['language']})" for t in approved
            )
        elif tpl.get("error"):
            result["hint"] = "Liste modèles: " + str(tpl["error"])
    return result
