"""The process entry point: configure logging, then serve stdio until the client disconnects.

``stdio`` is the transport every host (Claude Desktop, Cursor, the MCP Inspector) uses to launch a
local server: it speaks JSON-RPC over this process's stdin and stdout. That is why logging is
configured *first* and always writes to stderr — stdout is the wire. ``configure_logging`` replaces
the root handlers, so the SDK's ``logging.basicConfig`` call inside ``MCPServer`` becomes a no-op
and the stream keeps one shape (JSON in ``prod``, readable in ``dev``).

Roadmap 7.8's ``numenews mcp --transport stdio`` calls :func:`main` directly.
"""

from __future__ import annotations

from typing import Literal

from numenews.logging import configure_logging, get_logger
from numenews.mcp.server import build_server


def main(transport: Literal["stdio"] = "stdio") -> None:
    """Run the MCP server over ``transport`` until the client disconnects.

    Blocks for the life of the server. Phase 6 serves stdio only; the other transports
    the SDK offers (streamable HTTP, SSE) arrive with a use for them.
    """
    configure_logging()
    get_logger("numenews.mcp").info("mcp.starting", transport=transport)
    build_server().run(transport=transport)


if __name__ == "__main__":  # pragma: no cover - the module runner goes through __main__.py
    main()
