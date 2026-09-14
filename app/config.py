from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openrouter_api_key: str = ""
    nomic_api_key: str = ""
    database_url: str = ""
    openrouter_app_referer: str = "https://github.com/briefcast"
    dedup_threshold: float = 0.92


settings = Settings()
