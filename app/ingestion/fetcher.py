import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
import structlog

log = structlog.get_logger()

_HEADERS = {"User-Agent": "briefcast/0.1 (personal RSS reader; contact via GitHub)"}


async def fetch_rss(url: str) -> list[dict[str, Any]]:
    """Fetch an RSS/Atom feed and return normalised item dicts."""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=_HEADERS)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("fetcher.rss.http_error", url=url, error=str(exc))
            raise

    feed = feedparser.parse(response.content)

    items: list[dict[str, Any]] = []
    for entry in feed.entries:
        link = entry.get("link") or entry.get("id", "")
        if not link:
            continue
        title = (entry.get("title") or "").strip()
        if not title:
            continue

        author: str | None = None
        if entry.get("author"):
            author = entry.author
        elif entry.get("authors"):
            author = ", ".join(a.get("name", "") for a in entry.authors if a.get("name"))

        published_at: datetime | None = None
        if entry.get("published_parsed"):
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        elif entry.get("updated_parsed"):
            published_at = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

        items.append({
            "url": link,
            "title": title,
            "author": author,
            "published_at": published_at,
            "abstract": None,
        })

    log.info("fetcher.rss.done", url=url, item_count=len(items))
    return items


async def fetch_arxiv(query: str, max_results: int = 20) -> list[dict[str, Any]]:
    """Query the arXiv export API and return normalised item dicts (abstract included)."""
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://export.arxiv.org/api/query", params=params, headers=_HEADERS
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            log.error("fetcher.arxiv.http_error", query=query, error=str(exc))
            raise

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        url_elem = entry.find("atom:id", ns)
        if url_elem is None or not url_elem.text:
            continue
        url = url_elem.text.strip()

        title_elem = entry.find("atom:title", ns)
        title = " ".join((title_elem.text or "").split()) if title_elem is not None else ""
        if not title:
            continue

        abstract_elem = entry.find("atom:summary", ns)
        abstract = " ".join((abstract_elem.text or "").split()) if abstract_elem is not None else None

        authors = [
            name_elem.text
            for a in entry.findall("atom:author", ns)
            if (name_elem := a.find("atom:name", ns)) is not None and name_elem.text
        ]
        author = ", ".join(authors) if authors else None

        published_at: datetime | None = None
        pub_elem = entry.find("atom:published", ns)
        if pub_elem is not None and pub_elem.text:
            published_at = datetime.fromisoformat(pub_elem.text.rstrip("Z")).replace(
                tzinfo=timezone.utc
            )

        items.append({
            "url": url,
            "title": title,
            "author": author,
            "published_at": published_at,
            "abstract": abstract,
        })

    log.info("fetcher.arxiv.done", query=query, item_count=len(items))
    return items
