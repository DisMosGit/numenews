"""Shared pytest configuration.

The fixtures themselves land with ``ROADMAP.md`` 0.8; the ``--run-eval`` flag is here from the
first test so that ``make test-eval`` is a valid target while ``make test`` never collects the
evaluation suite (phase 9).
"""

from __future__ import annotations

import pytest


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
