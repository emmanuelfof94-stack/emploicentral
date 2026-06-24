"""
Lance une passe d'agrégation d'offres à la main (hors planificateur).

Usage:
    cd app/backend && set -a; . ../.env; set +a && ../.venv/bin/python run_aggregation.py
"""
import asyncio
import logging

from services.database import initialize_database, close_database
from services.job_aggregator import run_aggregation


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    await initialize_database()
    try:
        inserted = await run_aggregation()
        print(f"\n>>> {inserted} nouvelle(s) offre(s) insérée(s).")
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(main())
