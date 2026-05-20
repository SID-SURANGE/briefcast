import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "google/gemini-2.5-flash"

_PROMPT_TEMPLATE = (
    "You are a content classifier for a daily AI industry briefing aimed at technical practitioners.\n"
    "Decide whether the article belongs in this briefing.\n\n"
    "Answer YES if the article is primarily about any of these:\n"
    "- AI/ML models, research, benchmarks, or techniques (LLMs, diffusion, multimodal, etc.)\n"
    "- AI product launches, feature announcements, or demos\n"
    "- AI infrastructure: GPUs, TPUs, AI chips, AI cloud platforms\n"
    "- AI company news with a direct AI angle: funding, partnerships, acquisitions, leadership\n"
    "- AI safety, alignment, policy, or regulation\n"
    "- Robotics, autonomous systems, or AI agents\n"
    "- AI industry events and announcements (Google I/O, NeurIPS, ICML, OpenAI Dev Day, etc.)\n"
    "- Open-source AI tools, frameworks, datasets, or libraries\n\n"
    "Answer NO if the article is primarily about:\n"
    "- General software engineering, web dev, or DevOps with no AI component\n"
    "- Hardware, finance, or business news with no clear AI angle\n"
    "- Politics, sports, lifestyle, entertainment, or non-tech topics\n\n"
    "When in doubt, answer YES — it is better to include a borderline article than to miss a relevant one.\n\n"
    "Article title: TITLE_PLACEHOLDER\n"
    "Snippet: SNIPPET_PLACEHOLDER\n\n"
    "Reply with a single word: YES or NO."
)


async def is_ai_relevant(title: str, snippet: str = "") -> bool:
    """
    LLM-based relevance classifier. Replaces the hardcoded keyword filter.
    Uses Gemini Flash — same model as the summariser, cheapest option in the stack.
    Falls back to True on API error to avoid silently dropping articles.
    """
    prompt = (
        _PROMPT_TEMPLATE
        .replace("TITLE_PLACEHOLDER", title)
        .replace("SNIPPET_PLACEHOLDER", snippet[:400])
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings.openrouter_app_referer,
                },
                json={
                    "model": _MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 5,
                    "temperature": 0.0,
                },
            )
            response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip().upper()
        relevant = answer.startswith("YES")
        log.debug("classifier.result", title=title[:80], relevant=relevant, answer=answer)
        return relevant
    except Exception as exc:
        # Fail open — better to store a non-AI article than silently drop a real one
        log.warning("classifier.error", title=title[:80], error=str(exc))
        return True
