"""Smoke tests: the package imports and the phase-0 entry points behave."""

from __future__ import annotations

import asyncio
import json

import pytest

import numenews
from numenews.cli.__main__ import main as cli_main
from numenews.mcp import AppContext, build_server
from numenews.mcp.main import main as mcp_main


def test_package_exposes_version() -> None:
    """The package imports and reports the released version."""
    assert numenews.__version__ == "0.1.0"


async def test_asyncio_auto_mode_runs_coroutines() -> None:
    """`asyncio_mode = "auto"` runs coroutine tests without an explicit marker."""
    loop = asyncio.get_running_loop()

    assert loop.is_running()


def test_cli_placeholder_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI placeholder keeps stdout parseable as JSON."""
    assert cli_main() == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "not_implemented"


def test_mcp_entry_point_serves_the_phase_six_server() -> None:
    """The placeholder is gone: the package exposes a server and its main serves it."""
    assert callable(mcp_main)
    assert callable(build_server)
    assert AppContext.__name__ == "AppContext"
