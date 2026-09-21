"""The nine MCP tools, one plain function each.

A tool is an ordinary function: its name is the tool name, its docstring the description the model
reads, its type hints the input schema, and its return annotation the output schema (``MCPServer``
derives all four). The body is a thin wrapper — the work belongs to the layers below, and the only
things that happen here are the conversions of :mod:`numenews.mcp.schemas`, the
:func:`~numenews.mcp.context.AppContext` lookup that supplies the collaborators, and the
:func:`~numenews.mcp.errors.tool_errors` translation that turns an expected failure into a message
the model can act on.

The functions take a ``ctx: Context[AppContext]`` parameter, which the SDK injects and hides
from the schema; the lifespan object it carries is read with :func:`context_of`. They stay plain
callables —
:func:`numenews.mcp.server.build_server` registers them with ``MCPServer.add_tool`` — so a unit test
can import and call the ones that need no context directly.

``TOOLS`` is the registry the server iterates; it grows with roadmap 6.2-6.10, one tool per task.
"""

from __future__ import annotations

from collections.abc import Callable

from mcp.server.mcpserver import Context

from numenews.mcp.context import AppContext

#: Every tool the server registers, in roadmap order.
TOOLS: tuple[Callable[..., object], ...] = ()


def context_of(ctx: Context[AppContext]) -> AppContext:
    """Return the lifespan object the server handed this request.

    ``Context`` is the SDK's per-request object; the collaborators built once at startup live on the
    lifespan result it exposes. Every tool that needs one starts here, so the indirection is written
    down in one place.
    """
    return ctx.request_context.lifespan_context


__all__ = ["TOOLS", "context_of"]
