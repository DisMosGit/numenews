"""The Typer application itself: the entry point, the group callback and ``--version``.

These are unit tests because they exercise the CLI without a store, a model or a network: the stub
command of roadmap 7.1 is the only command so far, and ``--version`` answers from the package alone.
"""

from __future__ import annotations

import json

from typer.testing import CliRunner

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


def test_the_stub_command_writes_json_to_stdout() -> None:
    """``make run`` stays honest until 7.3 replaces the stub with the real ``today``."""
    result = runner.invoke(app, ["today"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["status"] == "not_implemented"


def test_no_pretty_writes_a_single_line() -> None:
    """``--no-pretty`` is the compact form, indented output being the default."""
    result = runner.invoke(app, ["--no-pretty", "today"])

    assert result.exit_code == 0
    assert result.stdout.count("\n") == 1
