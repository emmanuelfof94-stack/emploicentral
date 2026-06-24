"""
Planificateur de tâches de fond (APScheduler).

Démarre/arrête l'agrégation périodique des offres d'emploi externes. Branché
dans le `lifespan` de l'application (main.py).

Variables d'environnement:
- AGGREGATOR_ENABLED            (défaut: true)  active l'agrégation
- AGGREGATOR_INTERVAL_MINUTES   (défaut: 360)   fréquence en minutes
- AGGREGATOR_RUN_ON_STARTUP     (défaut: false) lance une 1re passe ~15s après le démarrage

Compatible Python 3.9.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.job_aggregator import (
    aggregator_enabled,
    interval_minutes,
    run_aggregation,
    _cfg_bool,
)

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


async def _aggregate_and_notify() -> None:
    """Job périodique : agrège les offres puis notifie les alertes correspondantes."""
    await run_aggregation()
    try:
        from services.notifications import dispatch_new_offer_alerts

        await dispatch_new_offer_alerts()
    except Exception as exc:  # pragma: no cover - défensif
        logger.error("Dispatch des alertes échoué: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Démarre le planificateur d'agrégation (idempotent)."""
    global _scheduler

    if not aggregator_enabled():
        logger.info("Scheduler: agrégateur désactivé (AGGREGATOR_ENABLED=false), non démarré")
        return
    if _scheduler is not None:
        logger.debug("Scheduler: déjà démarré")
        return

    mins = interval_minutes()
    run_on_startup = _cfg_bool("AGGREGATOR_RUN_ON_STARTUP", False)

    job_kwargs = dict(
        trigger=IntervalTrigger(minutes=mins),
        id="job_aggregation",
        replace_existing=True,
        max_instances=1,   # pas de chevauchement si une passe dure longtemps
        coalesce=True,     # fusionne les exécutions manquées
    )
    # IMPORTANT: ne passer next_run_time QUE pour forcer une passe au démarrage.
    # Le passer à None mettrait le job en pause (jamais exécuté); en l'omettant,
    # APScheduler calcule la 1re exécution = maintenant + intervalle.
    if run_on_startup:
        job_kwargs["next_run_time"] = datetime.now() + timedelta(seconds=15)

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(_aggregate_and_notify, **job_kwargs)
    _scheduler.start()
    logger.info(
        "Scheduler démarré: agrégation toutes les %d min%s",
        mins,
        " (1re passe dans ~15s)" if run_on_startup else "",
    )


async def stop_scheduler() -> None:
    """Arrête proprement le planificateur."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning("Scheduler: erreur à l'arrêt: %s", exc)
        _scheduler = None
        logger.info("Scheduler arrêté")
