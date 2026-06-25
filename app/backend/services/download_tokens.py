"""Jetons de téléchargement à usage unique (en mémoire).

Sert à télécharger un PDF via une navigation directe (Android refuse les blob:)
sans exposer le JWT longue durée dans l'URL. Le client demande un jeton court via
un POST authentifié, puis ouvre l'URL GET avec `?dl=<jeton>`. Le jeton est
à usage unique et expire vite.

Une seule machine en prod → état mémoire suffisant (voir services/rate_limit.py).
"""
from __future__ import annotations

import os
import secrets
import time
from threading import Lock
from typing import Dict, Optional, Tuple

TTL_SECONDS = max(30, int(os.environ.get("DOWNLOAD_TOKEN_TTL_SECONDS", 120)))

# token -> (user_id, expiry_epoch)
_tokens: Dict[str, Tuple[str, float]] = {}
_lock = Lock()


def _prune(now: float) -> None:
    expired = [t for t, (_, exp) in _tokens.items() if exp < now]
    for t in expired:
        _tokens.pop(t, None)


def issue(user_id: str) -> str:
    """Crée un jeton à usage unique lié à l'utilisateur."""
    now = time.time()
    token = secrets.token_urlsafe(24)
    with _lock:
        _prune(now)
        _tokens[token] = (user_id, now + TTL_SECONDS)
    return token


def consume(token: str) -> Optional[str]:
    """Valide ET invalide le jeton. Retourne l'user_id, ou None si invalide/expiré."""
    now = time.time()
    with _lock:
        _prune(now)
        entry = _tokens.pop(token, None)
    if not entry:
        return None
    user_id, exp = entry
    if exp < now:
        return None
    return user_id
