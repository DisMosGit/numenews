"""The Typer application itself: the entry point, the group callback and its arguments.

These are unit tests: every one exercises the CLI without a store, a model or a network, so a
failure here is about the parser or the version, never about a service. The command bodies are
tested in ``tests/integration/test_cli.py``, where an in-memory store can be injected.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from numenews.cli import main as cli_main
from numenews.cli.main import app

runner = CliRunner()


def test_version_prints_json_and_exits() -> None:
    """ROADMAP 7.1: ``--version`` works, and its answer honours the JSON-only contract."""
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
    """ROADMAP 7.8: ``numenews mcp`` proxies into ``mcp/main.py`` and writes no JSON of its own."""
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
    """Phase 6 serves stdio only; asking for HTTP is a usage error, not a silent fallback."""
    result = runner.invoke(app, ["mcp", "--transport", "http"])

    assert result.exit_code == 2
    assert result.stdout == ""
