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
EXPECTED_TOOLS: tuple[str, ...] = ("fetch_news", "extract_numbers", "compute_numerology")


async def test_the_registry_and_the_server_agree_on_the_tools(settings: Settings) -> None:
    """The registry drives registration, so a tool that is not in it is not a tool."""
    server = build_server(context=AppContext(settings))

    assert [tool.name for tool in await server.list_tools()] == list(EXPECTED_TOOLS)
    assert tuple(getattr(tool, "__name__", "") for tool in TOOLS) == EXPECTED_TOOLS


async def test_every_registered_tool_publishes_schemas(settings: Settings) -> None:
    """A tool without an input schema, a description or an output schema cannot be called."""
    server = build_server(context=AppContext(settings))

    for tool in await server.list_tools():
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None


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
