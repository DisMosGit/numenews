"""The server object: construction, registration and the stdout contract (ROADMAP 6.1).

``build_server`` is the seam the whole phase hangs on: it registers the tools of
:data:`numenews.mcp.tools.TOOLS`, wires the lifespan and accepts an injected application context.
The skeleton registers nothing — each tool task of 6.2-6.10 adds one entry to ``TOOLS`` and its name
to the expectation here — so this module also tracks the nine-tool surface as it grows.
"""

from __future__ import annotations

import pytest

from numenews.config import Settings
from numenews.mcp.context import AppContext
from numenews.mcp.server import SERVER_NAME, build_server
from numenews.mcp.tools import TOOLS

#: Every tool the finished server exposes, in roadmap order (6.2-6.10).
EXPECTED_TOOLS: tuple[str, ...] = ()


async def test_the_skeleton_registers_no_tools(settings: Settings) -> None:
    """ROADMAP 6.1's DoD: the server starts and ``list_tools`` returns an empty list."""
    server = build_server(context=AppContext(settings))

    assert await server.list_tools() == []
    assert tuple(getattr(tool, "__name__", "") for tool in TOOLS) == EXPECTED_TOOLS


async def test_the_server_reports_its_own_name(settings: Settings) -> None:
    """The name is the identity a client shows, so it is fixed by a constant."""
    server = build_server(context=AppContext(settings))

    assert server.name == SERVER_NAME
    assert SERVER_NAME == "numenews"


def test_building_a_server_writes_nothing_to_stdout(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    """stdout belongs to the JSON-RPC stream, so construction must not print to it."""
    build_server(context=AppContext(settings))

    assert capsys.readouterr().out == ""
