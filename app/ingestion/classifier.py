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
    "- New AI/ML model releases, launches, or demos (LLMs, diffusion, multimodal, etc.)\n"
    "- AI research: novel techniques, architectures, benchmarks, or findings\n"
    "- AI system design: training methods, inference optimisation, fine-tuning, RLHF, RAG, agents\n"
    "- Open-source AI tool or framework releases with a direct model/technique component\n"
    "- AI safety or alignment research techniques\n"
    "- AI industry events focused on model or research announcements (NeurIPS, ICML, OpenAI Dev Day, etc.)\n"
    "- LLM/AI observability and evaluation: tracing, prompt analytics, cost tracking,\n"
    "  hallucination detection, evaluation frameworks (LangSmith, Langfuse, Helicone, Braintrust, etc.)\n"
    "- AI system reliability: latency profiling, token budgeting, caching strategies for LLM pipelines\n\n"
    "Answer NO if the article is primarily about:\n"
    "- AI infrastructure, hardware, or cloud platforms (GPUs, TPUs, AI chips, data centres)\n"
    "- Robotics, autonomous vehicles, or physical AI systems\n"
    "- AI company funding, acquisitions, leadership, or business strategy with no model/research angle\n"
    "- AI policy, regulation, or governance without a technical research component\n"
    "- General software/DevOps observability with no AI/LLM component\n"
    "- Hardware, finance, business, politics, sports, lifestyle, or entertainment news\n"
    "- Domain-specific ML applications that do not advance core AI/ML techniques — e.g. using ML\n"
    "  for climate/weather, agriculture, hydrology, healthcare diagnostics, financial forecasting,\n"
    "  satellite imagery, or other applied science domains. The ML is a tool here, not the subject.\n\n"
    "When in doubt, answer NO — this briefing is for AI practitioners tracking the AI industry,\n"
    "not a general ML paper digest.\n\n"
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
