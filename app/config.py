from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    anthropic_api_key: str = ""
    nomic_api_key: str = ""
    telegram_bot_token: str = ""
    database_url: str = ""
    langchain_api_key: str = ""
    langchain_project: str = "briefcast-dev"
    langchain_tracing_v2: str = "false"
    dedup_threshold: float = 0.92


settings = Settings()
