"""Tests for the pydantic-settings configuration.

Each test runs from a temporary directory without a `.env` and with the known setting
variables removed, so the result depends only on what the test itself sets.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from numenews.config import Settings, get_settings

SETTINGS_ENV_VARS = (
    "ENVIRONMENT",
    "LOG_LEVEL",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "LLM_MODEL",
    "CACHE_DIR",
    "NEWSAPI_KEY",
)


@pytest.fixture(autouse=True)
def _isolated_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[None]:
    """Drop inherited setting variables, leave the working directory without `.env`."""
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults() -> None:
    """Every field has a usable default and no key is required."""
    settings = Settings()

    assert settings.environment == "dev"
    assert settings.log_level == "INFO"
    assert settings.qdrant_url.host == "localhost"
    assert settings.qdrant_url.port == 6333
    assert settings.qdrant_api_key is None
    assert settings.openai_api_key is None
    assert settings.openai_base_url is None
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.cache_dir == Path(".cache/hishel")
    assert settings.newsapi_key is None


def test_environment_variable_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """The process environment wins over the built-in defaults."""
    monkeypatch.setenv("QDRANT_URL", "http://qdrant.internal:6333")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("QDRANT_API_KEY", "secret-key")
    monkeypatch.setenv("NEWSAPI_KEY", "newsapi-secret")

    settings = Settings()

    assert settings.qdrant_url.host == "qdrant.internal"
    assert settings.qdrant_url.port == 6333
    assert settings.log_level == "DEBUG"
    assert settings.qdrant_api_key is not None
    assert settings.qdrant_api_key.get_secret_value() == "secret-key"
    assert settings.newsapi_key is not None
    assert settings.newsapi_key.get_secret_value() == "newsapi-secret"


def test_dotenv_is_read(tmp_path: Path) -> None:
    """`.env` in the working directory supplies values."""
    (tmp_path / ".env").write_text(
        "LLM_MODEL=local-model\nCACHE_DIR=.cache/from-dotenv\n",
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.llm_model == "local-model"
    assert settings.cache_dir == Path(".cache/from-dotenv")


def test_blank_values_are_ignored(tmp_path: Path) -> None:
    """Blank optional values behave as unset, the way `.env.example` ships them."""
    (tmp_path / ".env").write_text(
        "OPENAI_BASE_URL=\nOPENAI_API_KEY=\nQDRANT_API_KEY=\n",
        encoding="utf-8",
    )

    settings = Settings()

    assert settings.openai_base_url is None
    assert settings.openai_api_key is None
    assert settings.qdrant_api_key is None


def test_invalid_log_level_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown log level is rejected on start, not silently ignored."""
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings()


def test_invalid_qdrant_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed Qdrant URL is rejected on start."""
    monkeypatch.setenv("QDRANT_URL", "not a url")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_are_frozen() -> None:
    """Settings are immutable once validated."""
    settings = Settings()

    with pytest.raises(ValidationError):
        settings.log_level = "DEBUG"  # type: ignore[misc]  # frozen model, mypy cannot see it


def test_get_settings_is_cached() -> None:
    """`get_settings` returns one instance until the cache is cleared."""
    first = get_settings()

    assert get_settings() is first

    get_settings.cache_clear()

    assert get_settings() is not first
