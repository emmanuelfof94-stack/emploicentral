"""Quota d'accès aux formations + achat de l'accès illimité (candidat).

- `GET  /api/v1/training-access/quota`            → état du quota (pour l'UI).
- `POST /api/v1/training-access/purchase-request` → le candidat déclare avoir payé
  l'accès illimité (2 000 FCFA) ; une ligne `Course_purchases` (slug
  `formations-illimite`) est créée en `pending` et les admins sont notifiés.

La validation se fait via l'espace admin existant des achats de cours
(`/api/v1/course-access/admin/purchases/{id}/validate`) : passer le statut à
`paid` accorde automatiquement l'accès illimité (voir services.training_quota).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.auth import User
from models.course_purchases import Course_purchases
from models.notifications import Notification
from schemas.auth import UserResponse
from services import training_quota
from services.notifications import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/training-access", tags=["training-access"])

# Même numéro mobile money que les cours payants (surchargeable par env).
PAYMENT_NUMBER = (os.environ.get("PAYMENT_MOBILE_MONEY") or "+225 07 49 10 90 13").strip()


class QuotaResponse(BaseModel):
    limit: int
    used: int
    remaining: Optional[int] = None   # None = illimité
    unlimited: bool
    purchase_status: str              # none / pending / paid / rejected
    price: str
    payment_number: str


class PurchaseRequest(BaseModel):
    payment_ref: Optional[str] = None


async def _quota_response(db: AsyncSession, user_id: str) -> QuotaResponse:
    q = await training_quota.get_quota(db, user_id)
    return QuotaResponse(
        limit=q["limit"], used=q["used"], remaining=q["remaining"],
        unlimited=q["unlimited"], purchase_status=q["purchase_status"],
        price=q["price"], payment_number=PAYMENT_NUMBER,
    )


@router.get("/quota", response_model=QuotaResponse)
async def get_quota(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _quota_response(db, str(current_user.id))


@router.post("/purchase-request", response_model=QuotaResponse)
async def purchase_request(
    data: PurchaseRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uid = str(current_user.id)
    slug = training_quota.UNLIMITED_SLUG

    # Déjà illimité → rien à faire.
    if await training_quota.has_unlimited(db, uid):
        return await _quota_response(db, uid)

    # Réutilise/crée la ligne d'achat (une seule en cours par candidat).
    existing = (await db.execute(
        select(Course_purchases).where(
            Course_purchases.user_id == uid,
            Course_purchases.course_slug == slug,
        ).order_by(Course_purchases.id.desc()).limit(1)
    )).scalars().first()

    if existing and existing.status == "pending":
        existing.payment_ref = data.payment_ref or existing.payment_ref
    else:
        db.add(Course_purchases(
            user_id=uid, course_slug=slug, status="pending",
            payment_ref=(data.payment_ref or None), amount=training_quota.UNLIMITED_PRICE,
        ))
    await db.commit()

    await _notify_admins(db, current_user, data.payment_ref)
    return await _quota_response(db, uid)


async def _notify_admins(db: AsyncSession, candidate: UserResponse, payment_ref: Optional[str]) -> None:
    """Notifie les admins d'une demande d'achat d'accès illimité (best-effort)."""
    try:
        admins = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
        who = candidate.name or candidate.email or "Un candidat"
        title = f"💳 Demande d'achat : {training_quota.UNLIMITED_TITLE}"
        body = (f"{who} déclare avoir payé {training_quota.UNLIMITED_PRICE} "
                f"(réf : {payment_ref or '—'})")
        for a in admins:
            db.add(Notification(user_id=a.id, job_id=None, title=title, body=body,
                                channels="in_app,email", is_read=False))
        await db.commit()
        html = (
            f"<h2>{title}</h2>"
            f"<p><b>Candidat :</b> {who} ({candidate.email})</p>"
            f"<p><b>Produit :</b> {training_quota.UNLIMITED_TITLE}</p>"
            f"<p><b>Montant :</b> {training_quota.UNLIMITED_PRICE}</p>"
            f"<p><b>Référence de paiement :</b> {payment_ref or '—'}</p>"
            "<p>Vérifie la réception du paiement, puis valide l'accès depuis l'espace admin "
            "(Achats de cours).</p>"
        )
        for a in admins:
            if a.email:
                await send_email(a.email, title, html)
    except Exception as exc:  # noqa: BLE001 - la notif ne doit jamais bloquer la demande
        logger.warning("Notif admin (achat accès illimité) échouée: %s", exc)
