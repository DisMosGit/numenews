"""The MCP server: one ``MCPServer`` with the nine tools and the application lifespan.

The roadmap's 6.1 sketch said ``FastMCP("numenews")``. The installed SDK is v2, where that class was
renamed to ``MCPServer`` (``mcp.server.fastmcp`` no longer exists); the reasoning, and the rest of
the phase-6 decisions, are in ``docs/adr/0010-use-mcp-server.md``.

The server object is built by :func:`build_server` rather than created at import time, so a test can
hand it an :class:`~numenews.mcp.context.AppContext` over in-memory Qdrant and scripted agents. The
entry point of the process is :mod:`numenews.mcp.main`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server import MCPServer

from numenews import __version__
from numenews.config import get_settings
from numenews.logging import get_logger
from numenews.mcp.context import AppContext
from numenews.mcp.tools import TOOLS

logger = get_logger(__name__)

#: The name the client sees in ``serverInfo``.
SERVER_NAME = "numenews"

#: What the model is told about this server when it connects. The tool docstrings carry the details;
#: this is the one paragraph that says what the whole server is for.
SERVER_INSTRUCTIONS = (
    "Newspaper numerology: read numbers, dates and names out of the news and build a reading from "
    "them. fetch_news pulls articles for a topic and date range; extract_numbers reads the numbers "
    "out of a text; compute_numerology reduces a text to its numerological value; "
    "check_master_numbers reports 11/22/33; find_patterns connects stored articles; build_forecast "
    "returns a day's reading; query_qdrant searches the stored news and patterns by meaning; "
    "save_pattern keeps a connection; get_history says when a number was activated. The tools that "
    "read or write Qdrant need the vector store, the ones that reason need an LLM endpoint, and "
    "compute_numerology/check_master_numbers need nothing."
)


def build_server(*, context: AppContext | None = None) -> MCPServer[AppContext]:
    """Return the MCP server with every tool of :data:`~numenews.mcp.tools.TOOLS` registered.

    Args:
        context: The application context the tools reach through the lifespan. Built from
            :func:`numenews.config.get_settings` when omitted, which reads ``.env`` but touches no
            service: the collaborators inside it are built lazily, on the first call that needs one.

    Returns:
        A configured server. Nothing is connected yet; :meth:`~mcp.server.MCPServer.run` starts it.
    """
    app = context if context is not None else AppContext(get_settings())

    @asynccontextmanager
    async def lifespan(server: MCPServer[AppContext]) -> AsyncIterator[AppContext]:
        """Yield the context for the life of the server and close it on the way out."""
        logger.info("mcp.server.starting", tools=len(TOOLS))
        try:
            yield app
        finally:
            await app.aclose()
            logger.info("mcp.server.stopped")

    server: MCPServer[AppContext] = MCPServer(
        SERVER_NAME,
        version=__version__,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=lifespan,
        log_level=app.settings.log_level,
    )
    for tool in TOOLS:
        server.add_tool(tool)
    return server


__all__ = ["SERVER_INSTRUCTIONS", "SERVER_NAME", "build_server"]
