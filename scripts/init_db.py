"""
Lightweight DB initialisation for Docker Compose.
Runs Alembic migrations and syncs the source registry.
No HTTP calls — safe to run on every container startup (both operations are idempotent).

Usage:
    python scripts/init_db.py
"""
import subprocess
import sys

import structlog

from app.db import SessionLocal
from app.ingestion.registry import sync_sources
from app.observability.logger import configure_logging

log = structlog.get_logger()


def main() -> None:
    configure_logging()

    log.info("init_db.migrations_start")
    result = subprocess.run(["alembic", "upgrade", "head"])
    if result.returncode != 0:
        log.error("init_db.migrations_failed", returncode=result.returncode)
        sys.exit(1)
    log.info("init_db.migrations_done")

    log.info("init_db.seed_start")
    db = SessionLocal()
    try:
        inserted, updated = sync_sources(db)
        log.info("init_db.seed_done", inserted=inserted, updated=updated)
    finally:
        db.close()

    log.info("init_db.complete")


if __name__ == "__main__":
    main()
