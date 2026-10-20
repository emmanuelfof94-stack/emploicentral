"""Abonnement aux notifications push navigateur.

- `GET  /api/v1/push/config`      → {available, public_key} (public : le front décide
  d'afficher ou non le bouton « Activer les notifications »).
- `POST /api/v1/push/subscribe`   → enregistre l'abonnement du navigateur courant.
- `POST /api/v1/push/unsubscribe` → le supprime.
- `POST /api/v1/push/test`        → envoie une notification de test à soi-même.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.push_subscriptions import Push_subscriptions
from schemas.auth import UserResponse
from services import web_push

router = APIRouter(prefix="/api/v1/push", tags=["push"])


class PushConfig(BaseModel):
    available: bool
    public_key: Optional[str] = None


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/config", response_model=PushConfig)
async def config():
    if not web_push.push_available():
        return PushConfig(available=False)
    return PushConfig(available=True, public_key=web_push.vapid_public_key())


@router.post("/subscribe")
async def subscribe(
    data: SubscribeRequest,
    request: Request,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not data.endpoint.startswith("https://"):
        raise HTTPException(status_code=400, detail="Abonnement push invalide.")
    row = (await db.execute(
        select(Push_subscriptions).where(Push_subscriptions.endpoint == data.endpoint)
    )).scalars().first()
    ua = (request.headers.get("user-agent") or "")[:255]
    if row:
        # Même navigateur : on le rattache au compte connecté (changement de compte).
        row.user_id, row.p256dh, row.auth, row.user_agent = (
            str(current_user.id), data.keys.p256dh, data.keys.auth, ua)
    else:
        db.add(Push_subscriptions(user_id=str(current_user.id), endpoint=data.endpoint,
                                  p256dh=data.keys.p256dh, auth=data.keys.auth, user_agent=ua))
    await db.commit()
    return {"ok": True}


@router.post("/unsubscribe")
async def unsubscribe(
    data: UnsubscribeRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(Push_subscriptions).where(
        Push_subscriptions.endpoint == data.endpoint,
        Push_subscriptions.user_id == str(current_user.id),
    ))
    await db.commit()
    return {"ok": True}


@router.post("/test")
async def test(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not web_push.push_available():
        raise HTTPException(status_code=503, detail="Notifications push non configurées sur le serveur.")
    sent = await web_push.send_to_user(db, str(current_user.id), {
        "title": "EmploiCentral",
        "body": "Notifications activées : les nouvelles offres pour vous s'afficheront ici.",
        "url": "/jobs",
        "tag": "push-test",
    })
    if not sent:
        raise HTTPException(status_code=404, detail="Aucun appareil abonné n'a pu être joint.")
    return {"ok": True, "sent": sent}
