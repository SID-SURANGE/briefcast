"""
Web search fallback via Tavily API.

Used by responder.py when the local corpus has no relevant articles (similarity < threshold).
Tavily is purpose-built for LLM context: returns clean snippets, not raw HTML.

Free tier: 1,000 searches/month — sufficient for a personal assistant bot.
Set TAVILY_API_KEY in Railway env vars to enable. If unset, web search is silently disabled.
"""
import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web via Tavily and return structured results for LLM context.

    Returns list of dicts with keys: title, url, content, score.
    Returns empty list if TAVILY_API_KEY is unset or on any error (fail-safe).
    """
    if not settings.tavily_api_key:
        log.warning("web_searcher.disabled", reason="TAVILY_API_KEY not set")
        return []

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("web_searcher.http_error", error=str(exc))
        return []

    data = response.json()
    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0.0),
        }
        for r in data.get("results", [])
    ]

    log.info("web_searcher.done", query_len=len(query), results=len(results))
    return results


def build_web_context(results: list[dict]) -> str:
    """Format Tavily results into the same context-block shape that responder.py uses."""
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        snippet = r["content"][:400] + ("…" if len(r["content"]) > 400 else "")
        lines.append(
            f"[{i}] {r['title']}\n"
            f"    URL: {r['url']}\n"
            f"    {snippet}"
        )
    return "\n\n".join(lines)
