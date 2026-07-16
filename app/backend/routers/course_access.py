"""
Accès payant aux cours protégés (paiement mobile money manuel + validation admin).

Flux :
1. `GET  /api/v1/course-access/{slug}/status`  → l'utilisateur a-t-il accès ?
2. `POST /api/v1/course-access/{slug}/request`  → le candidat déclare avoir payé (pending) + notifie l'admin
3. Admin valide via `/admin/purchases/{id}/validate` → status=paid → accès débloqué
4. `GET  /api/v1/course-access/{slug}/content`   → sert le HTML du cours UNIQUEMENT aux ayants droit
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_admin_user, get_current_user
from models.auth import User
from models.course_purchases import Course_purchases
from models.notifications import Notification
from schemas.auth import UserResponse
from services.notifications import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/course-access", tags=["course-access"])

# Numéro mobile money où les candidats paient (Wave / Orange Money), surchargeable par env.
PAYMENT_NUMBER = (os.environ.get("PAYMENT_MOBILE_MONEY") or "+225 07 49 10 90 13").strip()

# Cours payants protégés : slug → métadonnées + fichier HTML servi.
# `sales_paused` suspend UNIQUEMENT les nouvelles demandes d'achat : les ayants droit
# (status=paid) conservent l'accès au contenu via /{slug}/content.
PAID_COURSES = {
    "pmp": {
        "title": "Préparation à la certification PMP (simulation d'examen)",
        "file": "pmp-simulation.html",
        "price": "20 000 FCFA",
        # Vente suspendue le temps de réécrire en questions originales les items
        # de la banque repris/traduits d'un livre tiers et du glossaire PMBOK.
        "sales_paused": True,
        "paused_reason": "Cette préparation est en cours de refonte : la banque de questions est "
                         "réécrite pour être 100 % originale. La vente rouvrira très bientôt.",
    },
}

_PROTECTED_DIR = Path(__file__).resolve().parent.parent / "protected_courses"


# ---------- Schemas ----------
class PurchaseRequest(BaseModel):
    payment_ref: Optional[str] = None


class AccessStatus(BaseModel):
    slug: str
    title: str
    price: str
    payment_number: str
    has_access: bool
    status: str  # none / pending / paid / rejected
    sales_paused: bool = False
    paused_reason: Optional[str] = None


class AdminPurchase(BaseModel):
    id: int
    user_id: str
    user_email: Optional[str] = None
    course_slug: str
    course_title: Optional[str] = None
    status: str
    payment_ref: Optional[str] = None
    amount: Optional[str] = None
    created_at: Optional[datetime] = None


# ---------- Helpers ----------
async def _latest_purchase(db: AsyncSession, user_id: str, slug: str) -> Optional[Course_purchases]:
    rows = (await db.execute(
        select(Course_purchases)
        .where(Course_purchases.user_id == user_id, Course_purchases.course_slug == slug)
        .order_by(Course_purchases.id.desc())
    )).scalars().all()
    return rows[0] if rows else None


def _course_or_404(slug: str) -> dict:
    course = PAID_COURSES.get(slug)
    if not course:
        raise HTTPException(status_code=404, detail="Cours introuvable.")
    return course


def _status(slug: str, course: dict, status: str) -> AccessStatus:
    return AccessStatus(
        slug=slug, title=course["title"], price=course["price"],
        payment_number=PAYMENT_NUMBER, has_access=(status == "paid"), status=status,
        sales_paused=bool(course.get("sales_paused")),
        paused_reason=course.get("paused_reason") if course.get("sales_paused") else None,
    )


async def _notify_admins(db: AsyncSession, title: str, body: str, html: str) -> None:
    try:
        admins = (await db.execute(select(User).where(User.role == "admin"))).scalars().all()
        for a in admins:
            db.add(Notification(user_id=a.id, job_id=None, title=title, body=body,
                                channels="in_app,email", is_read=False))
        await db.commit()
        for a in admins:
            if a.email:
                await send_email(a.email, title, html)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notif admin (achat cours) échouée: %s", exc)


async def _notify_user(db: AsyncSession, user_id: str, title: str, body: str) -> None:
    try:
        db.add(Notification(user_id=user_id, job_id=None, title=title, body=body,
                            channels="in_app,email", is_read=False))
        await db.commit()
        u = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
        if u and u.email:
            await send_email(u.email, title, f"<p>{body}</p><hr><p style='color:#888;font-size:12px'>EmploiCentral</p>")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notif candidat (achat cours) échouée: %s", exc)


# ---------- Endpoints candidat ----------
@router.get("/{slug}/status", response_model=AccessStatus)
async def access_status(
    slug: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = _course_or_404(slug)
    p = await _latest_purchase(db, str(current_user.id), slug)
    return _status(slug, course, p.status if p else "none")


@router.post("/{slug}/request", response_model=AccessStatus)
async def request_access(
    slug: str,
    data: PurchaseRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = _course_or_404(slug)
    p = await _latest_purchase(db, str(current_user.id), slug)
    if p and p.status == "paid":
        return _status(slug, course, "paid")
    # Vente suspendue : on refuse toute NOUVELLE demande, sans toucher aux accès déjà
    # accordés (retournés juste au-dessus) ni aux demandes en attente, que l'admin
    # peut toujours valider depuis son espace.
    if course.get("sales_paused"):
        raise HTTPException(status_code=403, detail=course.get("paused_reason")
                            or "La vente de ce cours est temporairement suspendue.")
    if p and p.status == "pending":
        p.payment_ref = (data.payment_ref or p.payment_ref)
    else:
        p = Course_purchases(
            user_id=str(current_user.id), course_slug=slug, status="pending",
            payment_ref=(data.payment_ref or None), amount=course["price"],
        )
        db.add(p)
    await db.commit()

    who = current_user.name or current_user.email or "Un candidat"
    title = f"💳 Demande d'achat : {course['title']}"
    body = f"{who} déclare avoir payé {course['price']} (réf : {data.payment_ref or '—'})"
    html = (
        f"<h2>{title}</h2><p><b>Candidat :</b> {who} ({current_user.email})</p>"
        f"<p><b>Cours :</b> {course['title']}</p><p><b>Montant :</b> {course['price']}</p>"
        f"<p><b>Référence de paiement :</b> {data.payment_ref or '—'}</p>"
        "<p>Vérifie la réception du paiement, puis valide l'accès depuis l'espace admin "
        "(Achats de cours).</p>"
    )
    await _notify_admins(db, title, body, html)
    return _status(slug, course, "pending")


@router.get("/{slug}/content")
async def course_content(
    slug: str,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = _course_or_404(slug)
    p = await _latest_purchase(db, str(current_user.id), slug)
    if not (p and p.status == "paid"):
        raise HTTPException(status_code=403, detail="Accès non autorisé : achat requis.")
    path = _PROTECTED_DIR / course["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Contenu du cours introuvable.")
    return FileResponse(str(path), media_type="text/html")


# ---------- Endpoints admin ----------
@router.get("/admin/purchases", response_model=List[AdminPurchase])
async def admin_list_purchases(
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Course_purchases).order_by(Course_purchases.id.desc())
    )).scalars().all()
    user_ids = list({r.user_id for r in rows})
    emails = {}
    if user_ids:
        for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all():
            emails[u.id] = u.email
    out = []
    for r in rows:
        out.append(AdminPurchase(
            id=r.id, user_id=r.user_id, user_email=emails.get(r.user_id),
            course_slug=r.course_slug,
            course_title=(PAID_COURSES.get(r.course_slug, {}).get("title") or r.course_slug),
            status=r.status, payment_ref=r.payment_ref, amount=r.amount, created_at=r.created_at,
        ))
    return out


@router.post("/admin/purchases/{purchase_id}/validate")
async def admin_validate(
    purchase_id: int,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Course_purchases).where(Course_purchases.id == purchase_id))).scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    p.status = "paid"
    uid = p.user_id
    title = PAID_COURSES.get(p.course_slug, {}).get("title", p.course_slug)
    await db.commit()
    await _notify_user(db, uid, "✅ Accès débloqué", f"Votre paiement pour « {title} » est validé. Vous pouvez maintenant accéder au cours.")
    return {"success": True}


@router.post("/admin/purchases/{purchase_id}/reject")
async def admin_reject(
    purchase_id: int,
    _admin: UserResponse = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Course_purchases).where(Course_purchases.id == purchase_id))).scalars().first()
    if not p:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    p.status = "rejected"
    uid = p.user_id
    title = PAID_COURSES.get(p.course_slug, {}).get("title", p.course_slug)
    await db.commit()
    await _notify_user(db, uid, "Paiement non confirmé", f"Votre paiement pour « {title} » n'a pas pu être confirmé. Vérifiez et soumettez à nouveau, ou contactez-nous.")
    return {"success": True}
