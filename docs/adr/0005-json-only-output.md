# 5. JSON-only stdout, and how a failure is reported

## Status

Accepted (phase 7)

## Date

2026-09-21

## Context

The one-shot CLI is the second interface over the same pipeline as the MCP server, and the phase that
introduces it also introduces the contract its callers will build on. Three questions had no answer in
the code before it:

**What does stdout carry?** `numenews today | jq .dominant_number` is the phase's definition of done,
so a command's answer has to be machine-readable. A CLI can print a Rich table instead, which is
friendlier to a human at a terminal and useless to a pipe; it can print both, which makes the output
neither. The project already has an answer for its other interface — every MCP tool returns a Pydantic
model — and `AGENTS.md` bans dicts at boundaries.

**What happens when a command cannot answer?** An unreachable Qdrant, an unconfigured model endpoint
and a missing collection are expected conditions with actionable fixes, not defects. Click's default is
a traceback on stderr and exit code 1; a caller piping stdout then sees an empty stream and has to parse
the log to learn what went wrong.

**Where do logs go?** `structlog` is already configured to write to stderr (phase 0.7), and the pipeline
logs one line per step. If any of that reached stdout, `jq` would choke on the first log record.

Two smaller questions came with them: whether the indentation of the JSON should be a per-command or a
per-invocation choice, and what `numenews mcp` — a long-running server behind the same application —
does with the contract.

## Decision

We will keep stdout for exactly one JSON document per command result, and put everything else on
stderr.

1. **Every command answers with a Pydantic model**, and `numenews.cli.output.print_json` is the only
   writer. It calls `model.model_dump_json(indent=2 if pretty else None)` and appends one newline. No
   command builds a dict, calls `print()` or renders a table; Rich paints `--help` and tracebacks only.
2. **Logs and progress go to stderr** through `structlog`, as everywhere else in the project. Each
   invocation binds a fresh correlation id, so the `cli.*` lines and the `pipeline.step` lines it
   triggers share one `request_id`.
3. **An expected domain failure is an answer too.** `numenews.mcp.errors.DOMAIN_ERRORS` — the same set
   the MCP tools translate — is caught by `run_command`, printed as `{"error": …, "kind": …}` on stdout,
   and exits `1`. `kind` is the exception class name so a script can branch without parsing the message.
4. **A usage error is not an answer.** A bad flag, an unknown command or a `--date` the grammar refuses
   is Click's usage error: message on stderr, exit `2`, stdout untouched. A pipe never sees a
   half-document.
5. **Unexpected exceptions stay loud.** Anything outside `DOMAIN_ERRORS` is a defect in this code base;
   it propagates with a traceback on stderr and an empty stdout, exactly as an MCP tool lets a defect
   crash instead of turning it into a quiet result.
6. **`--pretty/--no-pretty` is a group option** (default pretty): indentation renders one result, so it
   belongs to the invocation, not to each command.
7. **`--version` is JSON too** — `{"name": "numenews", "version": "0.1.0"}` — so the exception is part
   of the rule rather than an exception to it.
8. **Two documented writers are not command results:** Click's `--help`/usage text, and `numenews mcp`,
   whose stdout is the JSON-RPC wire of the long-running server.

## Consequences

Easier: `numenews <command> | jq …` works for every command and every failure; a test asserts the
contract with `json.loads` and `JSONDecoder().raw_decode` instead of scraping output; the CLI and the
MCP tools share their result models (`Forecast`, `CollectionQueryResult`) and their failure policy, so
the two interfaces cannot drift; adding a command means adding a model, which keeps the output typed.

Harder: a human who wants a rendered table gets none — the JSON is pretty-printed, not formatted. Logs
and the payload travel on separate streams, so a caller that merges them (`2>&1`) breaks the contract
it just piped into. Every new failure mode has to be classified: inside `DOMAIN_ERRORS` if a caller can
act on it, outside if it is a bug.

The `ErrorReport` shape is now a public interface: `error` is the human-readable message and `kind` the
exception class, and changing either is a breaking change for scripts. Adding fields is additive and
allowed.

## References

- `ROADMAP.md` phase 7 (7.1–7.10) and 6.1 (the `ToolError` policy this mirrors)
- [`../USER_FLOW.md`](../USER_FLOW.md) — the command surface this contract applies to
- [ADR 0006](0006-one-shot-vs-repl.md) — why the CLI is one-shot, and what shares its container
- [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) — "CLI stdout is JSON only"
