"""Tests for the shared fixtures themselves."""

from __future__ import annotations

from pathlib import Path

from numenews.config import Settings, get_settings


def test_settings_fixture_is_hermetic(settings: Settings, tmp_cache_dir: Path) -> None:
    """The settings fixture sees the temporary cache directory and no API keys."""
    assert settings.cache_dir == tmp_cache_dir
    assert settings.openai_api_key is None
    assert settings.qdrant_api_key is None
    assert settings.environment == "dev"


def test_tmp_cache_dir_is_wired_into_get_settings(tmp_cache_dir: Path) -> None:
    """`tmp_cache_dir` also moves the process-wide cached settings."""
    assert get_settings().cache_dir == tmp_cache_dir
