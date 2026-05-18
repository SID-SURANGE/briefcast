from datetime import datetime, timedelta, timezone

import pytest

from app.ranking.ranker import TIER_WEIGHTS, rank, score


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _article(
    source_tier: int = 2,
    published_at: datetime | None = None,
    embedding: list[float] | None = None,
) -> dict:
    return {
        "id": id(object()),  # unique id per call
        "source_tier": source_tier,
        "published_at": published_at or _now(),
        "embedding": embedding,
    }


# --- score() ---

def test_score_tier1_higher_than_tier2_same_recency() -> None:
    t1 = score(_article(source_tier=1), novelty=1.0)
    t2 = score(_article(source_tier=2), novelty=1.0)
    assert t1 > t2


def test_score_tier2_higher_than_tier3_same_recency() -> None:
    t2 = score(_article(source_tier=2), novelty=1.0)
    t3 = score(_article(source_tier=3), novelty=1.0)
    assert t2 > t3


def test_score_recent_higher_than_old_same_tier() -> None:
    recent = score(_article(published_at=_now() - timedelta(hours=1)), novelty=1.0)
    old = score(_article(published_at=_now() - timedelta(days=10)), novelty=1.0)
    assert recent > old


def test_score_14_day_old_recency_is_zero() -> None:
    just_expired = _article(published_at=_now() - timedelta(days=14, seconds=1))
    # recency component is 0; score = tier_weight*0.35 + 0*0.35 + novelty*0.30
    s = score(just_expired, novelty=0.0)
    expected = TIER_WEIGHTS[2] * 0.35
    assert abs(s - expected) < 1e-6


def test_score_is_in_unit_range() -> None:
    s = score(_article(source_tier=1, published_at=_now()), novelty=1.0)
    assert 0.0 <= s <= 1.0


def test_score_unknown_tier_uses_minimum_weight() -> None:
    # Unknown tier falls back to 0.5 (TIER_WEIGHTS.get default)
    s_unknown = score(_article(source_tier=99), novelty=0.0)
    s_tier3 = score(_article(source_tier=3), novelty=0.0)
    assert s_unknown == s_tier3


def test_score_none_published_at_uses_neutral_recency() -> None:
    # published_at=None → recency=0.5 (neutral fallback)
    s = score({"source_tier": 2, "published_at": None}, novelty=0.0)
    expected = TIER_WEIGHTS[2] * 0.35 + 0.5 * 0.35
    assert abs(s - expected) < 1e-6


# --- rank() ---

def test_rank_empty_list() -> None:
    assert rank([]) == []


def test_rank_returns_sorted_descending() -> None:
    articles = [
        _article(source_tier=3, published_at=_now() - timedelta(days=12)),
        _article(source_tier=1, published_at=_now() - timedelta(hours=1)),
        _article(source_tier=2, published_at=_now() - timedelta(days=3)),
    ]
    ranked = rank(articles)
    scores = [a["score"] for a in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_sets_score_on_each_article() -> None:
    articles = [_article(source_tier=1), _article(source_tier=2)]
    ranked = rank(articles)
    assert all("score" in a for a in ranked)
    assert all(isinstance(a["score"], float) for a in ranked)


def test_rank_tier1_leads_when_recency_equal() -> None:
    same_time = _now() - timedelta(hours=2)
    t1 = _article(source_tier=1, published_at=same_time)
    t2 = _article(source_tier=2, published_at=same_time)
    t3 = _article(source_tier=3, published_at=same_time)
    ranked = rank([t3, t2, t1])
    assert ranked[0]["source_tier"] == 1
    assert ranked[1]["source_tier"] == 2
    assert ranked[2]["source_tier"] == 3


def test_rank_novelty_penalises_duplicate_embeddings() -> None:
    # Two articles with identical embeddings should have lower novelty than a unique one
    shared_emb = [1.0] + [0.0] * 767
    unique_emb = [0.0, 1.0] + [0.0] * 766

    same_time = _now() - timedelta(hours=1)
    a1 = _article(source_tier=2, published_at=same_time, embedding=shared_emb)
    a2 = _article(source_tier=2, published_at=same_time, embedding=shared_emb)
    a3 = _article(source_tier=2, published_at=same_time, embedding=unique_emb)

    ranked = rank([a1, a2, a3])
    # a3 has unique embedding → higher novelty → should outscore the duplicates
    assert ranked[0]["score"] >= ranked[1]["score"]
    top_emb = ranked[0].get("embedding")
    assert top_emb == unique_emb


def test_rank_single_article_scores_without_error() -> None:
    articles = [_article(source_tier=1)]
    ranked = rank(articles)
    assert len(ranked) == 1
    assert "score" in ranked[0]
