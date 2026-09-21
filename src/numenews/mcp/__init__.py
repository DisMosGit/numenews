"""MCP server and its nine tools.

The server is one :class:`~mcp.server.MCPServer` built by
:func:`~numenews.mcp.server.build_server`; the tools live in :mod:`numenews.mcp.tools`, the
collaborators they share in :mod:`numenews.mcp.context`, the JSON-shaped argument schemas in
:mod:`numenews.mcp.schemas` and the failure policy in :mod:`numenews.mcp.errors`.

``python -m numenews.mcp`` (and ``make mcp``) serves the nine tools over stdio;
``docs/MCP_TOOLS.md``
documents the surface and ``docs/adr/0010-use-mcp-server.md`` records why it is built this way.
"""

from __future__ import annotations

from numenews.mcp.context import AppContext
from numenews.mcp.server import build_server

__all__ = ["AppContext", "build_server"]
