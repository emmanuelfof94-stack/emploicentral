"""Suivi des erreurs (Sentry), DÉSACTIVÉ par défaut.

Sentry n'est initialisé que si la variable d'environnement `SENTRY_DSN` est
définie (et non vide). Sans elle, rien ne change : le SDK n'est même pas importé.

Variables :
- `SENTRY_DSN`                 : DSN du projet Sentry (secret, à poser sur Render).
- `ENVIRONMENT`                : nom d'environnement remonté à Sentry (défaut « prod »).
- `SENTRY_TRACES_SAMPLE_RATE`  : part des requêtes tracées (défaut 0.05, borné à [0, 1]).

Confidentialité : `send_default_pii=False` (ni IP, ni cookies, ni en-têtes
d'auth), corps de requête jamais envoyés (CV, mots de passe…) et pas de
variables locales dans les stack traces (elles exposent le scope ASGI brut).
Compatible Python 3.9.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_TRACES_SAMPLE_RATE = 0.05


def _traces_sample_rate() -> float:
    raw = (os.environ.get("SENTRY_TRACES_SAMPLE_RATE") or "").strip()
    if not raw:
        return DEFAULT_TRACES_SAMPLE_RATE
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TRACES_SAMPLE_RATE
    return min(1.0, max(0.0, value))


def init_sentry() -> bool:
    """Initialise Sentry si `SENTRY_DSN` est défini. Renvoie True si actif."""
    dsn = (os.environ.get("SENTRY_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("SENTRY_DSN est défini mais sentry-sdk n'est pas installé : suivi des erreurs inactif")
        return False

    environment = (os.environ.get("ENVIRONMENT") or "prod").strip() or "prod"
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            send_default_pii=False,
            max_request_body_size="never",
            # Les variables locales des frames contiennent le scope ASGI brut (en-têtes
            # Authorization, IP…) que le nettoyage par défaut ne filtre pas.
            include_local_variables=False,
            traces_sample_rate=_traces_sample_rate(),
            integrations=[StarletteIntegration(), FastApiIntegration()],
        )
    except Exception as exc:  # noqa: BLE001 - un DSN invalide ne doit jamais empêcher le démarrage
        logger.warning("Initialisation Sentry échouée : %s", exc)
        return False
    logger.info("Sentry actif (environment=%s)", environment)
    return True
