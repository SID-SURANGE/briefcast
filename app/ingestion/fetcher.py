from typing import Any

import httpx
import structlog

log = structlog.get_logger()


async def fetch_rss(url: str) -> list[dict[str, Any]]:
    pass


async def fetch_arxiv(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    pass
