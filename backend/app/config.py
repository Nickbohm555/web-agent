from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    OPENAI_API_KEY: str
    SERPER_API_KEY: str
    CRAWLER_SESSION_PROFILES_PATH: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
