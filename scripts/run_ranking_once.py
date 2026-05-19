"""
Trigger a single ranking pass over articles ingested in the last 14 days.
Safe to run at any time — scores existing articles, writes nothing new.

Usage:
    .venv\\Scripts\\python scripts/run_ranking_once.py
"""
import asyncio

from app.observability.logger import configure_logging
from app.worker import run_ranking


async def main() -> None:
    configure_logging()
    print("Running ranking pass...")
    await run_ranking()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
