# MCP tools

`numenews` exposes nine tools over the Model Context Protocol. This document is the contract of that
surface: what each tool takes, what it returns, what it needs to be running, and how a client
connects. It is completed with the phase (roadmap 6.12); each tool section lands with its task.

- **Server name:** `numenews` (reported to the client as `serverInfo.name`).
- **Transport:** stdio. The host launches `uv run python -m numenews.mcp` (or `make mcp`) and speaks
  JSON-RPC over the process's stdin/stdout; logs go to stderr.
- **SDK:** the official Python SDK v2 (`MCPServer`). The class was called `FastMCP` in v1; the
  reasoning, including why v2 is used, is in [`adr/0010-use-mcp-server.md`](adr/0010-use-mcp-server.md).
- **Return values:** every tool returns a Pydantic model (or a list of them), so each call carries a
  typed `structuredContent` next to the text the model reads. No tool returns a bare dict.

## Prerequisites

Nothing is connected at startup. Each tool builds what it needs on its first call, and a missing
prerequisite comes back as a tool error with a message the model can act on:

| Tool group | Needs |
|---|---|
| `compute_numerology`, `check_master_numbers` | nothing |
| `extract_numbers` | an LLM endpoint (`OPENAI_API_KEY` or `OPENAI_BASE_URL`) |
| `fetch_news` | the news APIs (GDELT alone needs no key) |
| `query_qdrant`, `save_pattern`, `get_history` | Qdrant (`make dev`) |
| `find_patterns`, `build_forecast` | Qdrant and an LLM endpoint |

## Tools

_This table is filled in as roadmap 6.2-6.10 land; each row links to the section below it._

| Tool | Arguments | Returns | Task |
|---|---|---|---|
| — | — | — | 6.2-6.10 |

## Connecting a client

Connection snippets for Claude Desktop and Cursor are added with roadmap 6.11.
