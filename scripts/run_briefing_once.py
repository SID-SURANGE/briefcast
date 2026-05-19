"""
Trigger a single briefing composition and Telegram delivery.
Requires at least some ranked articles in the DB (run run_ranking_once.py first).

Usage:
    .venv\\Scripts\\python scripts/run_briefing_once.py
"""
import asyncio

from app.observability.logger import configure_logging
from app.worker import run_briefing


async def main() -> None:
    configure_logging()
    print("Composing and sending briefing...")
    await run_briefing()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
