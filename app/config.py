from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    nomic_api_key: str = ""
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


settings = Settings()
