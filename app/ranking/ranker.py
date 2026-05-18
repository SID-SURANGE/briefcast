from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

log = structlog.get_logger()

TIER_WEIGHTS: dict[int, float] = {1: 1.0, 2: 0.7, 3: 0.5}
_RECENCY_WINDOW_DAYS = 14.0


def score(article: dict[str, Any], novelty: float = 1.0) -> float:
    """
    Weighted ranking score in [0, 1].
    score = (tier_weight * 0.35) + (recency * 0.35) + (novelty * 0.30)
    """
    tier_weight = TIER_WEIGHTS.get(article.get("source_tier", 2), 0.5)
    recency = _recency(article.get("published_at"))
    return tier_weight * 0.35 + recency * 0.35 + novelty * 0.30


def rank(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Score every article (computing novelty pairwise from embeddings),
    write score back into each dict, and return sorted descending.
    """
    if not articles:
        return []

    novelty_scores = _compute_novelty(articles)
    for article, nov in zip(articles, novelty_scores):
        article["score"] = score(article, novelty=nov)

    articles.sort(key=lambda a: a["score"], reverse=True)
    log.info("ranker.done", article_count=len(articles), top_score=round(articles[0]["score"], 4))
    return articles


def _recency(published_at: datetime | None) -> float:
    """Linear decay: 1.0 at publish time → 0.0 at 14 days old. Clamps at both ends."""
    if published_at is None:
        return 0.5
    now = datetime.now(tz=timezone.utc)
    # Ensure published_at is tz-aware
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = (now - published_at).total_seconds() / 86400.0
    return float(max(0.0, 1.0 - age_days / _RECENCY_WINDOW_DAYS))


def _compute_novelty(articles: list[dict[str, Any]]) -> list[float]:
    """
    For each article: novelty = 1 - max cosine similarity to any other article.
    Falls back to 1.0 for articles without embeddings.
    """
    embeddings = [a.get("embedding") for a in articles]
    if not any(e is not None for e in embeddings):
        return [1.0] * len(articles)

    results: list[float] = []
    for i, emb_i in enumerate(embeddings):
        if emb_i is None:
            results.append(1.0)
            continue
        vi = np.array(emb_i, dtype=np.float32)
        norm_i = float(np.linalg.norm(vi))
        if norm_i == 0.0:
            results.append(1.0)
            continue
        max_sim = 0.0
        for j, emb_j in enumerate(embeddings):
            if i == j or emb_j is None:
                continue
            vj = np.array(emb_j, dtype=np.float32)
            norm_j = float(np.linalg.norm(vj))
            if norm_j > 0.0:
                sim = float(np.dot(vi, vj) / (norm_i * norm_j))
                if sim > max_sim:
                    max_sim = sim
        results.append(1.0 - max_sim)

    return results
