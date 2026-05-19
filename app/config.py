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
    dedup_threshold: float = 0.92


settings = Settings()
