# 6. One-shot commands instead of a REPL, and the container they share with MCP

## Status

Accepted (phase 7)

## Date

2026-09-21

## Context

Phase 7 gives the project its second interface. The MCP server already serves the same operations to a
long-lived client over stdio, so the CLI could have been anything: a REPL that keeps a pipeline warm, a
daemon that answers over a socket, or a batch of commands that each run once and exit. The choice
shapes how the code is written, tested and configured.

The forces are known from the rest of the project. State lives in Qdrant, never in process memory
(`AGENTS.md`), so a one-shot command is idempotent and resumable — that rule exists because the process
cannot remember anything between runs anyway. `AppContext` (phase 6.1) already knows how to build the
store, the agents, the pipeline and one cached HTTP client lazily and once, for exactly this kind of
caller; the MCP server holds one for the life of the process. A CLI invocation, by contrast, pays for
its own construction: a Qdrant health check, four `pydantic-ai` agents, and two `fastembed` sessions
that stay unloaded until the first `embed` (phase 3.1, ADR 0003). The two `bge` models (~286 MB) are
cached on disk, so the expensive part is paid once per machine, not once per command.

Testing had a vote too. A one-shot command is a function of its arguments, the store and the
environment, which `typer.testing.CliRunner` can drive in-process with an in-memory Qdrant and scripted
agents (the same doubles phases 5 and 6 use). A REPL would need a session protocol and a second test
harness for it.

## Decision

We will ship one-shot commands only. Each invocation parses its arguments, builds one `AppContext`,
runs one operation, prints one JSON document and closes the context; no command keeps state between
runs, and there is no REPL or daemon.

1. **`build_context(settings)` in `cli/main.py` is the container seam.** It returns a
   `numenews.mcp.context.AppContext` — the same lazy container the MCP server uses — rather than a
   second, CLI-only container. The CLI already has to import the MCP entry point for
   `numenews mcp` (roadmap 7.8), and duplicating the lazy-build logic would give the two interfaces
   two ways to build the same objects.
2. **One event loop per invocation.** `run_command` drives the async command body with `asyncio.run`,
   which is what "one-shot" means in process terms; there is no long-lived loop to keep warm.
3. **The context is closed on the way out**, success or failure, so no Qdrant connection or HTTP client
   outlives the command.
4. **`numenews mcp --transport stdio` is the long-running mode.** A caller that wants one process for
   many calls uses the MCP server, which is the interface designed for it.
5. **The tests replace `build_context`**, which is why it is a module-level function and not an inline
   `AppContext(...)` call: `CliRunner` covers the real parser, the real `run_command` and the real
   output path, while the services behind them are doubles.

## Consequences

Easier: every command is independently runnable, cron-able and pipe-able; a run is idempotent by
construction, because nothing survives it; the test harness needs no session management; and the
container stays in one place, so a fix to how the store is built (health check, error message) reaches
both interfaces at once.

Harder: each run re-checks Qdrant and re-constructs four agents, which is measurable but small next to a
model call, and unavoidable for a process that exits. Configuration is read once per process, so
changing `.env` mid-session changes nothing. There is no history, completion or `cd`-like context
between commands; a user who wants a conversation uses the MCP server. Finally, the CLI depends on
`numenews.mcp` for its container and its `mcp` command, so `mcp` is no longer a leaf package — the
interfaces share a layer, which `docs/ARCHITECTURE.md` records.

## References

- `ROADMAP.md` phase 7 (7.1–7.10) and phase 6.1 (`AppContext`)
- [`../USER_FLOW.md`](../USER_FLOW.md) — the commands and their prerequisites
- [ADR 0005](0005-json-only-output.md) — what those commands write to stdout
- [ADR 0011](0011-rag-pipeline-orchestration.md) — the pipeline each command calls
