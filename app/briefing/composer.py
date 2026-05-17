from typing import Any

import structlog

log = structlog.get_logger()


async def compose(articles: list[dict[str, Any]]) -> str:
    pass
