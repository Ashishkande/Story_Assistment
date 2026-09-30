"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_env: str = "development"
    secret_key: str = "change-me"
    log_level: str = "INFO"
    port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # LLM
    llm_provider: Literal["openai", "anthropic", "google"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://story_user:story_pass@localhost:5432/story_db"
    database_url_sync: str = "postgresql+psycopg2://story_user:story_pass@localhost:5432/story_db"

    # Cost & Retry Controls
    max_revisions: int = 2
    max_retries: int = 3
    max_tokens_per_episode: int = 4000
    max_cost_per_episode: float = 0.50
    max_cost_per_run: float = 5.00

    # Episode configuration
    episode_min_words: int = 400
    episode_max_words: int = 700
    total_episodes: int = 200

    # Features
    enable_embeddings: bool = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
