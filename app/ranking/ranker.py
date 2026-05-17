from typing import Any

import structlog

log = structlog.get_logger()

TIER_WEIGHTS = {1: 1.0, 2: 0.7, 3: 0.5}


def score(article: dict[str, Any]) -> float:
    pass


def rank(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pass
