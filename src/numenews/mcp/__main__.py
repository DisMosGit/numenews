"""Run the MCP server: ``python -m numenews.mcp``.

The one-shot CLI of phase 7 proxies to the same :func:`numenews.mcp.main.main`, so both entry points
start the identical server. stdout is the JSON-RPC stream and nothing else.
"""

from __future__ import annotations

from numenews.mcp.main import main

if __name__ == "__main__":
    main()
