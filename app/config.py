from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    nomic_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""  # your personal chat ID — get it from @userinfobot
    database_url: str = ""
    langsmith_api_key: str = ""
    langsmith_project: str = "briefcast-dev"
    langsmith_tracing: str = "false"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    openrouter_app_referer: str = "https://github.com/briefcast"
    dedup_threshold: float = 0.92
    # Minimum cosine similarity to treat a retrieved article as relevant for RAG.
    # Below this → corpus miss → Tavily web search fallback.
    # Calibrated from live corpus: irrelevant tech results score 0.52–0.59; genuine hits 0.65+.
    rag_min_similarity: float = 0.65
    # Web search fallback (Tavily — free tier: 1,000 searches/month)
    tavily_api_key: str = ""
    # Telegram Forum Topics — optional; if set, briefings/alerts post to specific threads.
    # Create a Supergroup, enable Topics, then get thread IDs from each topic's link.
    telegram_briefing_thread_id: int | None = None
    telegram_alert_thread_id: int | None = None


settings = Settings()
