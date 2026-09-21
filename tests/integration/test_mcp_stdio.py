"""The stdio transport, end to end (ROADMAP 6.11).

The in-memory tests of ``test_mcp_tools.py`` prove what each tool answers; this one proves the thing
a host actually does: launch ``uv run python -m numenews.mcp`` as a child process, speak JSON-RPC
over its stdin/stdout and list the tools. It is the substitute for the roadmap's manual "open it in
Claude Desktop" check — no Node, no GUI, and the same command ``make mcp`` runs.

The subprocess is only asked to initialize and list: nothing is built eagerly, so the check passes
on a machine with no Qdrant and no LLM key, which is exactly the phase-6 startup contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The nine tools of ROADMAP 6.2-6.10, in registration (roadmap) order.
EXPECTED_TOOLS = [
    "fetch_news",
    "extract_numbers",
    "compute_numerology",
    "find_patterns",
    "check_master_numbers",
    "build_forecast",
    "query_qdrant",
    "save_pattern",
    "get_history",
]


async def test_the_server_speaks_stdio_and_lists_nine_tools() -> None:
    """`make mcp`: the process starts, handshakes and publishes every tool with its schemas."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "numenews.mcp"],
        cwd=str(REPO_ROOT),
    )

    async with Client(params, raise_exceptions=True, read_timeout_seconds=60) as client:
        tools = await client.list_tools()

    assert [tool.name for tool in tools.tools] == EXPECTED_TOOLS
    for tool in tools.tools:
        assert tool.description
        assert tool.input_schema["type"] == "object"
        assert tool.output_schema is not None
        assert json.dumps(tool.input_schema)  # the schema is JSON-serializable, as the wire needs
