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

Both hosts launch the server as a child process and speak stdio. The command is the same one
`make mcp` runs; `uv` resolves the project from the directory the host uses as the working
directory, so no absolute path has to be committed.

### Cursor

The project-scoped config is committed as [`.cursor/mcp.json`](../.cursor/mcp.json):

```json
{
  "mcpServers": {
    "numenews": {
      "command": "uv",
      "args": ["run", "python", "-m", "numenews.mcp"]
    }
  }
}
```

### Claude Desktop

Claude Desktop reads `claude_desktop_config.json` from the user's own configuration directory
(`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows), so the entry is
not part of this repository. Add it with the absolute path of your checkout:

```json
{
  "mcpServers": {
    "numenews": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/numenews", "python", "-m", "numenews.mcp"]
    }
  }
}
```

Restart the host afterwards; both show the server's nine tools once the connection is up.

### Without a GUI

```bash
make mcp                                     # the server, waiting on stdin
uv run pytest tests/integration/test_mcp_stdio.py   # the same handshake, as a test
uv run python -m numenews.mcp                # the same, by module
```

`tests/integration/test_mcp_stdio.py` is the automated stand-in for the roadmap's manual
"open it in Claude Desktop" check.
