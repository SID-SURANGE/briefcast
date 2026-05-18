import time
from typing import Literal

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_NOMIC_URL = "https://api-atlas.nomic.ai/v1/embedding/text"
_MODEL = "nomic-embed-text-v1.5"

TaskType = Literal["search_document", "search_query"]


async def embed(text: str, task_type: TaskType = "search_document") -> list[float]:
    """Embed a single text. Use task_type='search_query' when embedding a RAG query."""
    results = await embed_batch([text], task_type=task_type)
    return results[0]


async def embed_batch(texts: list[str], task_type: TaskType = "search_document") -> list[list[float]]:
    """Embed a list of texts in one API call. Returns 768-dim float vectors (nomic-embed-text-v1.5)."""
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _NOMIC_URL,
                headers={
                    "Authorization": f"Bearer {settings.nomic_api_key}",
                    "Content-Type": "application/json",
                },
                json={"texts": texts, "model": _MODEL, "task_type": task_type},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("embedder.http_error", text_count=len(texts), error=str(exc))
        raise

    latency_ms = (time.monotonic() - t0) * 1000
    data = response.json()
    log.info(
        "nomic.embed",
        task_type=task_type,
        text_count=len(texts),
        latency_ms=round(latency_ms, 1),
    )
    return data["embeddings"]
