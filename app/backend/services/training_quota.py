"""Quota d'accès aux formations pour les candidats.

Règle produit : chaque candidat dispose de **5 accès gratuits à vie**. Consomment
1 accès : générer un parcours IA, ou débloquer une formation gratuite du catalogue.
Au-delà, le candidat peut acheter l'**accès illimité à vie** (2 000 FCFA, mobile
money validé manuellement par un admin — réutilise le flux `Course_purchases`).

L'accès illimité = au moins un achat `Course_purchases` au statut `paid` pour le
slug produit `formations-illimite`. Le compteur consommé = nombre de lignes dans
`Training_access_events` pour le candidat.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course_purchases import Course_purchases
from models.notifications import Notification
from models.training_access import Training_access_events

logger = logging.getLogger(__name__)

# Quota gratuit à vie.
FREE_ACCESS_LIMIT = 5

# Produit « accès illimité » (acheté via le flux Course_purchases existant).
UNLIMITED_SLUG = "formations-illimite"
UNLIMITED_TITLE = "Accès illimité aux formations"
UNLIMITED_PRICE = "2 000 FCFA"

# Titres exposés à l'admin pour les « produits » qui ne sont pas des cours protégés.
PRODUCT_TITLES = {UNLIMITED_SLUG: UNLIMITED_TITLE}

# Renvoyé dans le detail d'un 402 pour que le front affiche le paywall.
QUOTA_CODE = "quota_exhausted"


async def has_unlimited(db: AsyncSession, user_id: str) -> bool:
    """Le candidat a-t-il acheté (et fait valider) l'accès illimité ?"""
    row = (await db.execute(
        select(Course_purchases.id).where(
            Course_purchases.user_id == user_id,
            Course_purchases.course_slug == UNLIMITED_SLUG,
            Course_purchases.status == "paid",
        ).limit(1)
    )).first()
    return row is not None


async def used_count(db: AsyncSession, user_id: str) -> int:
    return int((await db.execute(
        select(func.count(Training_access_events.id))
        .where(Training_access_events.user_id == user_id)
    )).scalar() or 0)


async def latest_purchase_status(db: AsyncSession, user_id: str) -> str:
    p = (await db.execute(
        select(Course_purchases.status).where(
            Course_purchases.user_id == user_id,
            Course_purchases.course_slug == UNLIMITED_SLUG,
        ).order_by(Course_purchases.id.desc()).limit(1)
    )).scalar()
    return p or "none"


async def get_quota(db: AsyncSession, user_id: str) -> dict:
    """État complet du quota pour affichage front + décisions serveur."""
    unlimited = await has_unlimited(db, user_id)
    used = await used_count(db, user_id)
    remaining = None if unlimited else max(0, FREE_ACCESS_LIMIT - used)
    return {
        "limit": FREE_ACCESS_LIMIT,
        "used": used,
        "remaining": remaining,
        "unlimited": unlimited,
        "purchase_status": await latest_purchase_status(db, user_id),
        "slug": UNLIMITED_SLUG,
        "price": UNLIMITED_PRICE,
    }


async def _already_consumed(db: AsyncSession, user_id: str, kind: str, ref: Optional[str]) -> bool:
    if ref is None:
        return False
    row = (await db.execute(
        select(Training_access_events.id).where(
            Training_access_events.user_id == user_id,
            Training_access_events.kind == kind,
            Training_access_events.ref == ref,
        ).limit(1)
    )).first()
    return row is not None


async def has_remaining(db: AsyncSession, user_id: str) -> bool:
    """Reste-t-il au moins un accès (gratuit ou illimité) ?"""
    if await has_unlimited(db, user_id):
        return True
    return await used_count(db, user_id) < FREE_ACCESS_LIMIT


def quota_exhausted_error() -> HTTPException:
    """402 Payment Required — le front le distingue par le code HTTP."""
    return HTTPException(
        status_code=402,
        detail={
            "code": QUOTA_CODE,
            "message": (
                f"Vous avez utilisé vos {FREE_ACCESS_LIMIT} accès gratuits aux formations. "
                f"Débloquez l'accès illimité à vie pour {UNLIMITED_PRICE}."
            ),
        },
    )


BLOCK_NOTIF_TITLE = "🎓 Quota de formations gratuites atteint"


async def notify_quota_blocked(db: AsyncSession, user_id: str) -> None:
    """Notif in-app « quota atteint » (une seule non lue à la fois, anti-spam)."""
    try:
        existing = (await db.execute(
            select(Notification.id).where(
                Notification.user_id == user_id,
                Notification.title == BLOCK_NOTIF_TITLE,
                Notification.is_read == False,  # noqa: E712
            ).limit(1)
        )).first()
        if existing:
            return
        body = (
            f"Vous avez utilisé vos {FREE_ACCESS_LIMIT} accès gratuits aux formations. "
            f"Débloquez l'accès illimité à vie pour {UNLIMITED_PRICE}."
        )
        db.add(Notification(user_id=user_id, job_id=None, title=BLOCK_NOTIF_TITLE, body=body,
                            channels="in_app", is_read=False))
        await db.commit()
    except Exception as exc:  # noqa: BLE001 - la notif ne doit jamais bloquer la réponse
        logger.warning("Notif quota formations échouée: %s", exc)


async def consume(
    db: AsyncSession,
    user_id: str,
    kind: str,
    ref: Optional[str] = None,
    *,
    commit: bool = True,
) -> None:
    """Consomme 1 accès (ou lève un 402 si quota épuisé).

    Idempotent pour un même (kind, ref) : rebloquer une formation déjà débloquée
    ne reconsomme pas d'accès. Un accès illimité ne consomme jamais rien.
    """
    if await _already_consumed(db, user_id, kind, ref):
        return
    if not await has_remaining(db, user_id):
        raise quota_exhausted_error()
    # Les détenteurs de l'illimité n'ont pas besoin qu'on journalise leur usage,
    # mais le faire garde un historique cohérent et sans effet sur le quota.
    db.add(Training_access_events(user_id=user_id, kind=kind, ref=ref))
    if commit:
        await db.commit()
