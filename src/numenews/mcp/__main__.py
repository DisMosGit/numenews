"""Placeholder entry point for the MCP server.

The ``FastMCP`` server and its nine tools land with phase 6 (``ROADMAP.md`` 6.1). Until then
this module keeps ``make mcp`` runnable: it reports the placeholder status on stderr and
exits successfully, leaving stdout free for the JSON-RPC stream the real server speaks.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Report the placeholder status on stderr and return the exit code."""
    print(
        "numenews MCP server is not implemented yet; the nine tools land in ROADMAP.md phase 6.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
