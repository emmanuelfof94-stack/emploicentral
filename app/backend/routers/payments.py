"""
Paiement automatique Wave Checkout pour les produits payants (cours protégés,
accès illimité aux formations), en complément du flux manuel de `course_access`.

Flux :
1. `POST /api/v1/payments/wave/checkout` {slug} → session Wave → le front redirige
   vers `wave_launch_url` (appli Wave / page de paiement).
2. Wave renvoie le candidat sur `/paiement/retour?checkout=<id>` ; le front interroge
   `GET /api/v1/payments/wave/checkout/{id}` qui relit la session CHEZ WAVE (jamais
   sur la foi du navigateur) et débloque l'accès si `payment_status == succeeded`.
3. En parallèle, `POST /api/v1/payments/wave/webhook` (signé) fait la même chose,
   même si le candidat ferme l'appli avant le retour.

Le déblocage est idempotent : il inscrit (ou passe à `paid`) la ligne
`course_purchases`, que le reste de l'appli utilise déjà pour les droits d'accès.
"""
from __future__ import annotations

import json
import logging
import os
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from models.course_purchases import Course_purchases
from models.wave_checkouts import Wave_checkouts
from routers.course_access import PAID_COURSES, _latest_purchase, _notify_admins, _notify_user
from schemas.auth import UserResponse
from services import training_quota, wave

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments/wave", tags=["payments"])

SITE_URL = (os.environ.get("PUBLIC_SITE_URL") or "https://emploicentral.onrender.com").rstrip("/")


# ---------- Schemas ----------
class CheckoutRequest(BaseModel):
    slug: str


class CheckoutStarted(BaseModel):
    checkout_id: int
    launch_url: str


class CheckoutState(BaseModel):
    checkout_id: int
    slug: str
    status: str  # pending / paid / failed / expired


# ---------- Produits ----------
def _product(slug: str) -> dict:
    """Titre + prix d'un produit actuellement EN VENTE, sinon 404/403."""
    course = PAID_COURSES.get(slug)
    if course:
        if course.get("sales_paused"):
            raise HTTPException(status_code=403, detail=course.get("paused_reason")
                                or "La vente de ce cours est temporairement suspendue.")
        return {"title": course["title"], "price": course["price"]}
    if slug == training_quota.UNLIMITED_SLUG:
        if not training_quota.quota_enabled():
            raise HTTPException(status_code=403, detail="Les formations sont actuellement en accès libre.")
        return {"title": training_quota.UNLIMITED_TITLE, "price": training_quota.UNLIMITED_PRICE}
    raise HTTPException(status_code=404, detail="Produit introuvable.")


def _title(slug: str) -> str:
    return PAID_COURSES.get(slug, {}).get("title") or training_quota.PRODUCT_TITLES.get(slug) or slug


def _same_amount(a: Optional[str], b: Optional[str]) -> bool:
    try:
        return a is not None and b is not None and Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return False


def _state(row: Wave_checkouts) -> str:
    if row.payment_status == "succeeded":
        return "paid"
    if row.checkout_status == "expired":
        return "expired"
    if row.payment_status == "cancelled":
        return "failed"
    return "pending"


# ---------- Réconciliation ----------
async def _apply_session(db: AsyncSession, row: Wave_checkouts, session: dict) -> None:
    """Met à jour la tentative depuis une session Wave et débloque l'accès si payé.

    Contrôles avant tout déblocage : même session, même référence, même montant,
    devise XOF. Idempotent (webhook en double, retour + webhook…).
    """
    s = wave.session_summary(session)
    if s["id"] != row.session_id or s["client_reference"] != f"ec-{row.id}":
        logger.warning("Wave: session incohérente pour checkout %s (%s)", row.id, s["id"])
        return
    row.checkout_status = s["checkout_status"] or row.checkout_status
    row.payment_status = s["payment_status"] or row.payment_status
    row.transaction_id = s["transaction_id"] or row.transaction_id

    paid = s["payment_status"] == "succeeded"
    if paid and not (_same_amount(s["amount"], row.amount) and s["currency"] == wave.CURRENCY):
        logger.error("Wave: montant/devise inattendus pour checkout %s : %s %s (attendu %s XOF)",
                     row.id, s["amount"], s["currency"], row.amount)
        row.payment_status = "amount_mismatch"
        await db.commit()
        return
    if not paid or row.purchase_id:
        await db.commit()
        return

    purchase = await _latest_purchase(db, row.user_id, row.product_slug)
    ref = f"Wave {row.transaction_id or row.session_id}"
    already_paid = bool(purchase and purchase.status == "paid")
    if purchase and not already_paid:
        purchase.status, purchase.payment_ref = "paid", ref
    elif not purchase:
        purchase = Course_purchases(user_id=row.user_id, course_slug=row.product_slug, status="paid",
                                    payment_ref=ref, amount=f"{row.amount} FCFA")
        db.add(purchase)
    await db.flush()
    row.purchase_id = purchase.id
    await db.commit()

    if not already_paid:
        title = _title(row.product_slug)
        await _notify_user(db, row.user_id, "✅ Paiement reçu — accès débloqué",
                           f"Votre paiement Wave pour « {title} » est confirmé. Bon apprentissage !")
        await _notify_admins(db, f"💰 Paiement Wave reçu : {title}",
                             f"{row.amount} FCFA payés via Wave (transaction {row.transaction_id or '—'}).",
                             f"<h2>Paiement Wave reçu</h2><p><b>Produit :</b> {title}</p>"
                             f"<p><b>Montant :</b> {row.amount} FCFA</p>"
                             f"<p><b>Transaction :</b> {row.transaction_id or '—'}</p>"
                             "<p>Accès débloqué automatiquement — aucune action requise.</p>")


# ---------- Endpoints ----------
@router.get("/config")
async def wave_config():
    return {"enabled": wave.wave_enabled()}


@router.post("/checkout", response_model=CheckoutStarted)
async def start_checkout(
    data: CheckoutRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not wave.wave_enabled():
        raise HTTPException(status_code=503, detail="Le paiement Wave n'est pas encore activé.")
    product = _product(data.slug)
    user_id = str(current_user.id)
    existing = await _latest_purchase(db, user_id, data.slug)
    if existing and existing.status == "paid":
        raise HTTPException(status_code=409, detail="Vous avez déjà accès à ce produit.")

    row = Wave_checkouts(user_id=user_id, product_slug=data.slug, amount=wave.amount_xof(product["price"]))
    db.add(row)
    await db.flush()  # → row.id, utilisé comme référence client
    back = f"{SITE_URL}/paiement/retour?checkout={row.id}"
    try:
        session = await wave.create_checkout_session(
            amount=row.amount, client_reference=f"ec-{row.id}",
            success_url=back, error_url=f"{back}&echec=1",
        )
    except wave.WaveError as exc:
        await db.rollback()
        logger.error("Wave: création de session échouée : %s", exc)
        raise HTTPException(status_code=502, detail="Wave est momentanément indisponible. Réessayez.")
    s = wave.session_summary(session)
    if not s["id"] or not s["wave_launch_url"]:
        await db.rollback()
        raise HTTPException(status_code=502, detail="Réponse Wave inattendue. Réessayez.")
    row.session_id, row.checkout_status, row.payment_status = s["id"], s["checkout_status"], s["payment_status"]
    await db.commit()
    return CheckoutStarted(checkout_id=row.id, launch_url=s["wave_launch_url"])


@router.get("/checkout/{checkout_id}", response_model=CheckoutState)
async def checkout_state(
    checkout_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Wave_checkouts).where(Wave_checkouts.id == checkout_id))).scalars().first()
    if not row or row.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Paiement introuvable.")
    # Tant que ce n'est pas tranché, on relit la session chez Wave (source de vérité).
    if _state(row) == "pending" and row.session_id and wave.wave_enabled():
        try:
            await _apply_session(db, row, await wave.get_checkout_session(row.session_id))
        except wave.WaveError as exc:
            logger.warning("Wave: relecture de la session %s échouée : %s", row.session_id, exc)
    return CheckoutState(checkout_id=row.id, slug=row.product_slug, status=_state(row))


@router.post("/webhook", include_in_schema=False)
async def wave_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw = await request.body()  # corps BRUT : indispensable à la vérification de signature
    if not wave.verify_webhook_signature(raw, request.headers.get("Wave-Signature", ""), wave.webhook_secret()):
        raise HTTPException(status_code=401, detail="Signature invalide.")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Corps illisible.")
    if event.get("type") not in ("checkout.session.completed", "checkout.session.payment_failed"):
        return {"received": True}  # autres événements (test, b2b…) : ignorés
    data = event.get("data") or {}
    row = (await db.execute(select(Wave_checkouts).where(Wave_checkouts.session_id == data.get("id")))).scalars().first()
    if not row:
        logger.warning("Wave webhook: session inconnue %s", data.get("id"))
        return {"received": True}  # 2xx : inutile que Wave réessaie pendant 3 jours
    await _apply_session(db, row, data)
    return {"received": True}
