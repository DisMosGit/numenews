"""Typed application settings, read from the environment and an optional ``.env``.

The values are validated on start, so a typo surfaces immediately instead of at the first
network call. Nothing here is required: the default demo path needs no API keys
(``AGENTS.md``), and every field has a working default.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type Environment = Literal["dev", "prod"]


class Settings(BaseSettings):
    """Runtime configuration for the CLI, the MCP server and the pipeline.

    The process environment wins over ``.env``, and both are case-insensitive.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # `.env` templates keep unused endpoints as blank lines; treating those as
        # unset avoids validation errors on `OPENAI_BASE_URL=` and `QDRANT_API_KEY=`.
        env_ignore_empty=True,
        # A developer's `.env` collects settings for Docker, editors and shells too;
        # foreign keys are none of this application's business.
        extra="ignore",
        # Settings are read once and never written back (use `model_copy` to derive).
        frozen=True,
    )

    # Where and how the process runs: `prod` renders one JSON object per log line.
    environment: Environment = "dev"
    log_level: LogLevel = "INFO"

    # Qdrant — the vector store that holds collections, payload indexes and history.
    # The default matches `docker-compose.yml`; the local container has no auth.
    qdrant_url: AnyHttpUrl = AnyHttpUrl("http://localhost:6333")
    qdrant_api_key: SecretStr | None = None

    # LLM — any OpenAI-compatible endpoint (OpenAI, OpenRouter, local Ollama).
    openai_api_key: SecretStr | None = None
    openai_base_url: AnyHttpUrl | None = None
    llm_model: str = "gpt-4o-mini"

    # hishel's RFC 9111 cache directory for news HTTP responses.
    cache_dir: Path = Path(".cache/hishel")

    # News APIs — every key is optional. A source without its key is simply not queried, so the
    # default demo path needs no configuration (AGENTS.md) and a half-configured machine still
    # produces a result from the feeds that are available.
    newsapi_key: SecretStr | None = None
    gnews_key: SecretStr | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance.

    Cached so that every layer shares one validated configuration; tests clear the cache
    with ``get_settings.cache_clear()`` after changing the environment.
    """
    return Settings()
