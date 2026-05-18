"""
Trigger a single ingestion + ranking cycle without starting the scheduler.

Usage:
    .venv\\Scripts\\python scripts/run_ingestion_once.py
"""
import asyncio

from app.observability.logger import configure_logging
from app.worker import run_ingestion


async def main() -> None:
    configure_logging()
    print("Starting one-shot ingestion (fetch -> dedup -> summarise -> embed -> rank)...")
    await run_ingestion()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
