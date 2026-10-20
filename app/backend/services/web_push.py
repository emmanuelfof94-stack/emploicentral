"""Notifications push navigateur (Web Push, protocole VAPID).

Configuration (variables d'environnement) :
- `VAPID_PUBLIC_KEY`  : clé publique (base64url), transmise au navigateur ;
- `VAPID_PRIVATE_KEY` : clé privée (base64url), reste sur le serveur ;
- `VAPID_SUBJECT`     : contact de l'émetteur (`mailto:…`), exigé par les services push.
Générer une paire : `python scripts/generate_vapid_keys.py` (racine du dépôt).

Sans clés, la fonctionnalité est simplement désactivée (`push_available()` faux) :
rien ne casse, le front masque le bouton d'activation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.push_subscriptions import Push_subscriptions

logger = logging.getLogger(__name__)


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def vapid_public_key() -> str:
    return _env("VAPID_PUBLIC_KEY")


def push_available() -> bool:
    return bool(_env("VAPID_PUBLIC_KEY") and _env("VAPID_PRIVATE_KEY"))


def _send_sync(sub: Dict[str, str], payload: Dict[str, Any]) -> int:
    """Envoie un message à UN abonnement. Renvoie le code HTTP du service push
    (201 = accepté ; 404/410 = abonnement expiré, à supprimer)."""
    from pywebpush import WebPushException, webpush

    try:
        resp = webpush(
            subscription_info={"endpoint": sub["endpoint"],
                               "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=_env("VAPID_PRIVATE_KEY"),
            vapid_claims={"sub": _env("VAPID_SUBJECT") or "mailto:contact@emploicentral.app"},
            ttl=24 * 3600,
        )
        return getattr(resp, "status_code", 201) or 201
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0) or 0
        logger.info("Web push refusé (%s): %s", status, str(exc)[:200])
        return status


async def send_to_user(session: AsyncSession, user_id: str, payload: Dict[str, Any]) -> int:
    """Envoie `payload` à tous les navigateurs abonnés de l'utilisateur.

    `payload` : {"title", "body", "url", "tag"?}. Les abonnements expirés (404/410)
    sont supprimés. Renvoie le nombre d'envois acceptés. Ne lève jamais."""
    if not push_available():
        return 0
    try:
        subs = (await session.execute(
            select(Push_subscriptions).where(Push_subscriptions.user_id == user_id)
        )).scalars().all()
        sent, dead = 0, []
        for s in subs:
            status = await asyncio.to_thread(
                _send_sync, {"endpoint": s.endpoint, "p256dh": s.p256dh, "auth": s.auth}, payload
            )
            if status in (404, 410):
                dead.append(s.id)
            elif 200 <= status < 300:
                s.last_success_at = datetime.now()
                sent += 1
        if dead:
            await session.execute(delete(Push_subscriptions).where(Push_subscriptions.id.in_(dead)))
        await session.commit()
        return sent
    except Exception as exc:  # noqa: BLE001 - le push est best-effort
        logger.warning("Envoi push échoué (user=%s): %s", user_id, exc)
        return 0


async def users_with_subscriptions(session: AsyncSession) -> List[str]:
    return list(set((await session.execute(select(Push_subscriptions.user_id))).scalars().all()))
