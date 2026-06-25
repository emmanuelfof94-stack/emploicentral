"""Limiteur de tentatives en mémoire (anti-force-brute), sans dépendance externe.

Adapté au déploiement actuel : une seule machine (SQLite mono-writer), donc un
état en mémoire processus suffit. Si on passe un jour à plusieurs instances, il
faudra externaliser ce compteur (Redis, etc.).

Usage typique (connexion) :
    blocked, retry_after = too_many_attempts(key)
    if blocked: -> 429 avec Retry-After
    ... vérifier les identifiants ...
    if echec: record_failure(key)
    else:     reset(key)
"""
from __future__ import annotations

import os
import time
from threading import Lock
from typing import Dict, List, Tuple

# Réglages (surchargeables par variables d'environnement).
MAX_ATTEMPTS = max(1, int(os.environ.get("LOGIN_MAX_ATTEMPTS", 5)))
WINDOW_SECONDS = max(1, int(os.environ.get("LOGIN_WINDOW_SECONDS", 900)))   # 15 min
BLOCK_SECONDS = max(1, int(os.environ.get("LOGIN_BLOCK_SECONDS", 900)))     # 15 min

_failures: Dict[str, List[float]] = {}
_lock = Lock()


def _prune(timestamps: List[float], now: float) -> List[float]:
    """Ne garde que les échecs encore dans la fenêtre glissante."""
    cutoff = now - WINDOW_SECONDS
    return [t for t in timestamps if t >= cutoff]


def too_many_attempts(key: str) -> Tuple[bool, int]:
    """Retourne (bloqué, secondes_avant_réessai). Ne modifie pas le compteur."""
    now = time.time()
    with _lock:
        attempts = _prune(_failures.get(key, []), now)
        _failures[key] = attempts
        if len(attempts) >= MAX_ATTEMPTS:
            # Bloqué jusqu'à BLOCK_SECONDS après le dernier échec.
            retry_after = int(max(0, attempts[-1] + BLOCK_SECONDS - now))
            if retry_after > 0:
                return True, retry_after
            # Le blocage a expiré → on repart à zéro.
            _failures.pop(key, None)
    return False, 0


def record_failure(key: str) -> None:
    now = time.time()
    with _lock:
        attempts = _prune(_failures.get(key, []), now)
        attempts.append(now)
        _failures[key] = attempts


def reset(key: str) -> None:
    """À appeler après une connexion réussie pour effacer les échecs."""
    with _lock:
        _failures.pop(key, None)
