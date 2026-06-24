"""In-app notifications API (liste + marquage lu)."""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.notifications import Notification
from schemas.auth import UserResponse

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
