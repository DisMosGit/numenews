"""The Typer application itself: the entry point, the group callback and its arguments.

These are unit tests: every one exercises the CLI without a store, a model or a network, so a
failure here is about the parser, the version or the shutdown, never about a service. The command
bodies are tested in ``tests/integration/test_cli.py``, where an in-memory store can be injected.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from numenews.cli import commands
from numenews.cli import main as cli_main
from numenews.cli.main import app
from numenews.config import Settings
from numenews.mcp.context import AppContext
from numenews.models import Forecast
from numenews.news.errors import NewsSourceError
from numenews.vector.errors import VectorStoreError

runner = CliRunner()


class _FailingClose:
    """A context whose cleanup fails, standing in for a store that cannot be closed."""

    async def aclose(self) -> None:
        raise VectorStoreError("the cleanup failed")


async def _failing_body(context: AppContext, *, topic: str) -> Forecast:
    """Stand in for ``commands.today`` when the body itself is the failure."""
    raise NewsSourceError("the body failed")


async def _answering_body(context: AppContext, *, topic: str) -> Forecast:
    """Stand in for ``commands.today`` when the body answers and only the cleanup can fail."""
    return Forecast(
        date=date(2026, 9, 21),
        dominant_number=7,
        master_active=False,
        forecast="День под знаком семи.",
        advice="Смотрите на детали.",
    )


def test_version_prints_json_and_exits() -> None:
    """cli-surface: ``--version`` works, and its answer honours the JSON-only contract."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"name": "numenews", "version": "0.1.0"}


def test_the_app_lists_its_commands() -> None:
    """``--help`` names the command surface a caller can invoke."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "today" in result.stdout


def test_without_arguments_it_shows_help() -> None:
    """A bare ``numenews`` is a usage error, not a silent no-op."""
    result = runner.invoke(app, [])

    assert result.exit_code == 2
    assert "Usage" in result.stdout


def test_an_unknown_command_is_a_usage_error() -> None:
    """A mistyped command exits 2 with the message on stderr and nothing on stdout."""
    result = runner.invoke(app, ["tody"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "tody" in result.stderr


def test_an_unknown_option_is_a_usage_error() -> None:
    """A mistyped flag is caught by the parser before any command body runs."""
    result = runner.invoke(app, ["--colour", "today"])

    assert result.exit_code == 2
    assert result.stdout == ""


def test_mcp_serves_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """cli-surface: ``numenews mcp`` proxies into ``mcp/main.py`` and writes no JSON of its own."""
    transports: list[str] = []
    monkeypatch.setattr(cli_main, "serve_mcp", transports.append)

    result = runner.invoke(app, ["mcp", "--transport", "stdio"])

    assert result.exit_code == 0
    assert transports == ["stdio"]
    assert result.stdout == ""


def test_mcp_defaults_to_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    """The transport has a default, so the terse ``numenews mcp`` works."""
    transports: list[str] = []
    monkeypatch.setattr(cli_main, "serve_mcp", transports.append)

    result = runner.invoke(app, ["mcp"])

    assert result.exit_code == 0
    assert transports == ["stdio"]


def test_mcp_refuses_an_unknown_transport() -> None:
    """mcp-surface serves stdio only; asking for HTTP is a usage error, not a silent fallback."""
    result = runner.invoke(app, ["mcp", "--transport", "http"])

    assert result.exit_code == 2
    assert result.stdout == ""


def test_build_context_returns_a_lazy_container(settings: Settings) -> None:
    """The default seam builds one ``AppContext`` and touches nothing: no Qdrant, no client."""
    context = cli_main.build_context(settings)

    assert isinstance(context, AppContext)
    assert context.settings is settings


def test_a_failing_body_outranks_a_failing_cleanup(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The failure a command reports is the body's, even when closing the context also fails."""
    monkeypatch.setattr(cli_main, "build_context", lambda settings: _FailingClose())
    monkeypatch.setattr(commands, "today", _failing_body)

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["kind"] == "NewsSourceError"
    assert "the body failed" in report["error"]
    assert "the cleanup failed" not in report["error"]
    assert "cli.command.cleanup_failed" in result.stderr


def test_a_cleanup_failure_after_an_answer_is_still_reported(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closing the context is part of the run, so with nothing else broken its failure is fatal."""
    monkeypatch.setattr(cli_main, "build_context", lambda settings: _FailingClose())
    monkeypatch.setattr(commands, "today", _answering_body)

    result = runner.invoke(app, ["today"])

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["kind"] == "VectorStoreError"
    assert "the cleanup failed" in report["error"]
    assert "cli.command.complete" not in result.stderr
