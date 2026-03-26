from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    AGENT_DATABASE_URL: str
    OPENAI_API_KEY: str
    SERPER_API_KEY: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
