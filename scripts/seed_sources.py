"""
Verify feed URLs live, then upsert all registry sources into the DB.

Usage:
    .venv\\Scripts\\python scripts/seed_sources.py
"""
import asyncio

import httpx

from app.db import SessionLocal
from app.ingestion.registry import SOURCES, SourceDefinition, sync_sources


async def _verify_rss(url: str) -> tuple[bool, str]:
    """Return (ok, reason). Checks HTTP status and that response looks like XML/RSS."""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "briefcast/0.1"})
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        ct = r.headers.get("content-type", "")
        if not any(t in ct for t in ("xml", "rss", "atom", "text")):
            return False, f"unexpected content-type: {ct}"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def main() -> None:
    print("Briefcast — source seed")
    print("=" * 50)

    verified: dict[str, bool] = {}
    for src in SOURCES:
        if src.feed_type == "arxiv_api":
            print(f"  [SKIP VERIFY] {src.name}  (verified-official API)")
            verified[src.name] = True
            continue
        ok, reason = await _verify_rss(src.feed_url)
        status = "OK  " if ok else "FAIL"
        print(f"  [{status}] {src.name}  —  {src.feed_url}")
        if not ok:
            print(f"         reason: {reason}")
        verified[src.name] = ok

    live = sum(verified.values())
    print(f"\n{live}/{len(SOURCES)} sources reachable")
    print()

    db = SessionLocal()
    try:
        inserted, updated = sync_sources(db)
        print(f"DB sync: {inserted} inserted, {updated} updated")

        total = db.execute(__import__("sqlalchemy").text("SELECT COUNT(*) FROM sources")).scalar()
        print(f"sources table now has {total} row(s)")
    finally:
        db.close()

    failed = [name for name, ok in verified.items() if not ok]
    if failed:
        print(f"\nFailed feeds (circuit breaker will handle at runtime):")
        for name in failed:
            print(f"  - {name}")

    print("\nDone. Run scripts/run_ingestion_once.py to trigger a live fetch.")


if __name__ == "__main__":
    asyncio.run(main())
