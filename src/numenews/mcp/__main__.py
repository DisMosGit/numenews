"""Placeholder entry point for the MCP server.

The ``FastMCP`` server and its nine tools land with phase 6 (``ROADMAP.md`` 6.1). Until then
this module keeps ``make mcp`` runnable: it reports the placeholder status on stderr and exits
successfully, leaving stdout free for the JSON-RPC stream the real server speaks.
"""

from __future__ import annotations

from numenews.logging import configure_logging, get_logger


def main() -> int:
    """Report the placeholder status on stderr and return the exit code."""
    configure_logging()
    get_logger("numenews.mcp").warning(
        "mcp.server_not_implemented",
        detail="the nine tools land in ROADMAP.md phase 6",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
