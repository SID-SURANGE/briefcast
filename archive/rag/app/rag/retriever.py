from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models.article import Article

log = structlog.get_logger()

_WINDOW_DAYS = 14


def retrieve(
    query_embedding: list[float],
    db: Session,
    k: int = 10,
    tier: int | None = None,
) -> list[dict[str, Any]]:
    """
    Cosine similarity search over the last 14 days of articles.
    Returns up to k results sorted by similarity descending.
    Optional tier filter restricts to a specific source tier.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=_WINDOW_DAYS)
    distance_col = Article.embedding.cosine_distance(query_embedding).label("distance")

    q = db.query(Article, distance_col).filter(
        Article.deleted_at.is_(None),
        Article.embedding.is_not(None),
        Article.published_at >= cutoff,
    )

    if tier is not None:
        q = q.filter(Article.source_tier == tier)

    q = q.order_by(distance_col).limit(k)

    rows = q.all()

    results = [
        {
            "title": article.title,
            "summary": article.summary or "",
            "source_name": article.source_name,
            "source_tier": article.source_tier,
            "url": article.url,
            "published_at": article.published_at,
            "similarity": round(1.0 - float(distance), 4),
        }
        for article, distance in rows
    ]

    log.info("retriever.done", query_k=k, returned=len(results))
    return results
