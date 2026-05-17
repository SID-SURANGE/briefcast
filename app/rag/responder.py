from typing import Any

import structlog

log = structlog.get_logger()


async def respond(query: str, context: list[dict[str, Any]]) -> str:
    pass
