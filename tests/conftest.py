"""Shared pytest fixtures.

Fixtures are hermetic on purpose: `settings` sees neither the developer's `.env` nor the
exported environment, so a result does not depend on the machine the suite runs on. The
`--run-eval` flag, registered here, keeps the ragas suite out of `make test`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from numenews.config import Settings, get_settings

# Every variable `Settings` reads, derived from the model so a new field cannot be forgotten.
SETTING_ENV_VARS: tuple[str, ...] = tuple(name.upper() for name in Settings.model_fields)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--run-eval`` flag that gates the ``eval`` marker."""
    parser.addoption(
        "--run-eval",
        action="store_true",
        default=False,
        help="Run tests marked `eval` (ragas metrics, phase 9).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``eval``-marked tests unless ``--run-eval`` was passed."""
    if config.getoption("--run-eval"):
        return
    skip_eval = pytest.mark.skip(reason="eval tests need --run-eval")
    for item in items:
        if "eval" in item.keywords:
            item.add_marker(skip_eval)


@pytest.fixture
def tmp_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Return a temporary hishel cache directory and point ``CACHE_DIR`` at it."""
    cache_dir = tmp_path / "hishel"
    cache_dir.mkdir()
    monkeypatch.setenv("CACHE_DIR", str(cache_dir))
    get_settings.cache_clear()
    yield cache_dir
    get_settings.cache_clear()


@pytest.fixture
def settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tmp_cache_dir: Path,
) -> Iterator[Settings]:
    """Return :class:`Settings` that cannot see the developer's environment or ``.env``.

    The working directory moves to an empty temporary directory, every setting variable is
    dropped (except the ``CACHE_DIR`` set by :func:`tmp_cache_dir`) and the
    :func:`numenews.config.get_settings` cache is cleared around the test.
    """
    for name in SETTING_ENV_VARS:
        if name != "CACHE_DIR":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()
