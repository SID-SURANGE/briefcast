from typing import Any

import structlog

log = structlog.get_logger()


async def retrieve(query_embedding: list[float], k: int = 10) -> list[dict[str, Any]]:
    pass
