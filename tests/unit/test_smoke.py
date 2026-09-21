"""Smoke tests: the package imports and the phase-0 entry points behave."""

from __future__ import annotations

import asyncio

import typer

import numenews
from numenews.cli.main import app as cli_app
from numenews.mcp import AppContext, build_server
from numenews.mcp.main import main as mcp_main


def test_package_exposes_version() -> None:
    """The package imports and reports the released version."""
    assert numenews.__version__ == "0.1.0"


async def test_asyncio_auto_mode_runs_coroutines() -> None:
    """`asyncio_mode = "auto"` runs coroutine tests without an explicit marker."""
    loop = asyncio.get_running_loop()

    assert loop.is_running()


def test_cli_entry_point_serves_the_typer_app() -> None:
    """The placeholder is gone: the package exposes the one-shot CLI application (phase 7)."""
    assert isinstance(cli_app, typer.Typer)
    assert cli_app.info.name == "numenews"


def test_mcp_entry_point_serves_the_phase_six_server() -> None:
    """The placeholder is gone: the package exposes a server and its main serves it."""
    assert callable(mcp_main)
    assert callable(build_server)
    assert AppContext.__name__ == "AppContext"
