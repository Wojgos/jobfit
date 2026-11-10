from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must match the vector column size in the database schema.
EMBEDDING_DIM = 768


def normalize_database_url(url: str) -> str:
    """Accept the URL a hosting provider gives you (e.g. Neon) and adapt it for asyncpg.

    ``postgres://`` / ``postgresql://`` become ``postgresql+asyncpg://``; libpq-only query
    options are translated (``sslmode`` -> ``ssl``) or dropped (``channel_binding``).
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    query = []
    for key, value in parse_qsl(parts.query):
        if key == "sslmode":
            query.append(("ssl", value))
        elif key != "channel_binding":
            query.append((key, value))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    # Values pasted into Secret Manager from a terminal often end with a newline.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", str_strip_whitespace=True)

    database_url: str = "postgresql+asyncpg://jobfit:jobfit@localhost:5433/jobfit"

    # "fake" runs fully offline with deterministic heuristics (tests, demos without an API key).
    llm_provider: Literal["gemini", "fake"] = "fake"
    google_api_key: str | None = None
    # Older Gemini models are closed to new API users; override with LLM_MODEL if needed.
    llm_model: str = "gemini-3.8-flash"
    embedding_model: str = "gemini-embedding-001"

    cors_origins: list[str] = ["http://localhost:4200"]
    agent_max_steps: int = 5

    # Public demo: sample data, CV upload and deletion disabled, nightly reset.
    demo_mode: bool = False
    admin_token: str | None = None
    # LLM-backed requests (analysis, cover letter, assistant) allowed per client IP per hour.
    rate_limit_per_hour: int = 20
    # Directory with the built Angular app; when set, the API also serves the frontend.
    static_dir: str | None = None

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    return Settings()
