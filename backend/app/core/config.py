from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match the vector column size in the database schema.
EMBEDDING_DIM = 768


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://jobfit:jobfit@localhost:5433/jobfit"

    # "fake" runs fully offline with deterministic heuristics (tests, demos without an API key).
    llm_provider: Literal["gemini", "fake"] = "fake"
    google_api_key: str | None = None
    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"

    cors_origins: list[str] = ["http://localhost:4200"]
    agent_max_steps: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
