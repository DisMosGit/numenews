"""Smoke tests: the package imports and the phase-0 entry points behave."""

from __future__ import annotations

import json

import pytest

import numenews
from numenews.cli.__main__ import main as cli_main
from numenews.mcp.__main__ import main as mcp_main


def test_package_exposes_version() -> None:
    """The package imports and reports the released version."""
    assert numenews.__version__ == "0.1.0"


def test_cli_placeholder_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI placeholder keeps stdout parseable as JSON."""
    assert cli_main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "not_implemented"


def test_mcp_placeholder_leaves_stdout_empty(capsys: pytest.CaptureFixture[str]) -> None:
    """The MCP placeholder reports on stderr only."""
    assert mcp_main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "mcp.server_not_implemented" in captured.err
