import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from app.briefing.composer import compose
from app.db import SessionLocal
from app.delivery.telegram_bot import send_alert, send_briefing
from app.ingestion.circuit_breaker import record_failure, record_success
from app.ingestion.classifier import is_ai_relevant
from app.ingestion.dedup import is_duplicate, l1_hash
from app.ingestion.fetcher import fetch_arxiv, fetch_rss
from app.models.article import Article
from app.models.source import Source
from app.observability.logger import configure_logging
from app.processing.embedder import embed
from app.processing.summariser import summarise
from app.ranking.ranker import rank

log = structlog.get_logger()

_ITEM_TIMEOUT_S = 90  # max seconds per article: classify + embed + summarise + embed


async def _ingest_source(source_id: int) -> int:
    """Fetch, dedup, summarise and persist articles for one source.

    Opens its own DB session so a long-running source cannot exhaust a shared
    connection that Railway's proxy might close after ~5 minutes of inactivity.
    Returns new article count.
    """
    db = SessionLocal()
    try:
        source = db.get(Source, source_id)
        if source is None:
            return 0

        t0 = time.monotonic()
        try:
            if source.feed_type == "rss":
                items = await fetch_rss(source.feed_url)
            elif source.feed_type == "arxiv_api":
                items = await fetch_arxiv(source.feed_url)
            else:
                log.warning("worker.unknown_feed_type", source=source.name, feed_type=source.feed_type)
                return 0
            record_success(source.name, db)
            source.last_fetched_at = datetime.now(tz=timezone.utc)
            db.commit()
        except Exception as exc:
            log.error("worker.fetch_error", source=source.name, error=str(exc))
            record_failure(source.name, db)
            if source.circuit_breaker_state == "degraded":
                await send_alert(
                    f"<b>{source.name}</b> has been paused after "
                    f"{source.consecutive_failures} failed fetches in a row.\n\n"
                    f"It will be skipped until the source recovers. "
                    f"Check the feed URL or source availability."
                )
            return 0

        new_count = 0
        for idx, item in enumerate(items, start=1):
            try:
                # L1 check: free hash lookup before any API call
                h = l1_hash(item["url"])
                if db.query(Article).filter(Article.dedup_hash == h, Article.deleted_at.is_(None)).first():
                    log.debug("worker.item_skip_l1", source=source.name, idx=idx, total=len(items))
                    continue

                snippet = item.get("abstract") or item.get("summary") or ""
                if not await is_ai_relevant(item["title"], snippet):
                    log.debug("worker.item_skip_irrelevant", source=source.name, title=item["title"][:80])
                    continue

                log.info("worker.item_processing", source=source.name, idx=idx, total=len(items), title=item["title"][:80])

                async def _process_item(
                    _item: dict = item, _storage_mode: str = source.storage_mode, _source_name: str = source.name
                ) -> tuple[str, list[float]]:
                    title_embedding = await embed(_item["title"], task_type="search_document")
                    if is_duplicate(_item["url"], title_embedding, db):
                        return "", []
                    if _storage_mode == "abstract_metadata":
                        summary_text = _item.get("abstract") or _item["title"]
                    else:
                        summary_text = await summarise(
                            _item["title"], _item.get("abstract") or _item["title"], _source_name
                        )
                    summary_embedding = await embed(summary_text, task_type="search_document")
                    return summary_text, summary_embedding

                try:
                    summary_text, summary_embedding = await asyncio.wait_for(
                        _process_item(), timeout=_ITEM_TIMEOUT_S
                    )
                except asyncio.TimeoutError:
                    log.warning("worker.item_timeout", source=source.name, idx=idx, url=item.get("url"))
                    continue

                if not summary_text:
                    continue

                article = Article(
                    url=item["url"],
                    title=item["title"],
                    author=item.get("author"),
                    source_name=source.name,
                    source_tier=source.tier,
                    published_at=item.get("published_at"),
                    summary=summary_text,
                    embedding=summary_embedding,
                    dedup_hash=h,
                    storage_mode=source.storage_mode,
                )
                db.add(article)
                db.commit()
                new_count += 1
            except Exception as exc:
                log.error("worker.item_error", source=source.name, url=item.get("url"), error=str(exc))
                db.rollback()

        log.info(
            "worker.source_done",
            source=source.name,
            fetched=len(items),
            new=new_count,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )
        return new_count
    finally:
        db.close()


async def run_ingestion() -> None:
    """Fetch all active sources, dedup, summarise, embed and persist. Runs every 6h."""
    log.info("worker.ingestion_start")
    db = SessionLocal()
    try:
        source_ids = [
            row.id for row in db.query(Source.id)
            .filter(Source.deleted_at.is_(None), Source.circuit_breaker_state != "degraded")
            .all()
        ]
    finally:
        db.close()

    total_new = 0
    for source_id in source_ids:
        total_new += await _ingest_source(source_id)
    log.info("worker.ingestion_done", sources=len(source_ids), total_new=total_new)

    await run_ranking()


async def run_ranking() -> None:
    """Score all articles published within the last 14 days and persist scores."""
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=14)
    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .filter(Article.published_at >= cutoff, Article.deleted_at.is_(None))
            .all()
        )
        if not articles:
            return

        article_dicts: list[dict[str, Any]] = [
            {
                "id": a.id,
                "source_tier": a.source_tier,
                "published_at": a.published_at,
                "embedding": a.embedding,
            }
            for a in articles
        ]
        ranked = rank(article_dicts)
        score_by_id = {d["id"]: d["score"] for d in ranked}
        for article in articles:
            article.score = score_by_id.get(article.id)
        db.commit()
        log.info("worker.ranking_done", scored=len(articles))
    finally:
        db.close()


async def run_briefing() -> None:
    """Select top-ranked articles, compose via Haiku, deliver via Telegram. Runs at 03:30 UTC (09:00 IST)."""
    # 36h window: covers today's articles + 12h buffer for ingestion lag.
    # The 14-day window is for RAG only — briefing must only show fresh articles.
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=36)
    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .filter(
                Article.published_at >= cutoff,
                Article.score.is_not(None),
                Article.deleted_at.is_(None),
            )
            .order_by(Article.score.desc())
            .limit(20)
            .all()
        )
        if not articles:
            log.warning("worker.briefing_no_articles")
            await send_briefing(
                "📭 <b>No new articles today</b>\n\n"
                "Nothing fresh from your sources in the last 36 hours — "
                "the pipeline is healthy, sources just had a quiet cycle.\n\n"
                "Next ingestion runs every 6 hours. You can still ask questions — the 14-day corpus is available.",
                [],
            )
            return

        article_dicts = [
            {
                "id": a.id,
                "title": a.title,
                "summary": a.summary or "",
                "source_name": a.source_name,
                "source_tier": a.source_tier,
                "url": a.url,
                "score": a.score,
                "published_at": a.published_at,
                "embedding": a.embedding,
            }
            for a in articles
        ]

        briefing_text, source_keys, shown_urls = await compose(article_dicts)
        if briefing_text:
            await send_briefing(briefing_text, source_keys, shown_urls)
            log.info("worker.briefing_done")
    finally:
        db.close()


async def main() -> None:
    configure_logging()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(run_ingestion, "cron", hour="*/6", minute=0)
    scheduler.add_job(run_briefing, "cron", hour=3, minute=30)
    scheduler.start()
    log.info("worker.started")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
