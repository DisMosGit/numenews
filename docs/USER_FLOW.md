# The one-shot CLI

> Phase 7. `ROADMAP.md` is the authoritative status; this document is the contract of the command
> surface: what each command does, what it needs, what it prints, and how it fails. The decisions
> behind it are in [ADR 0005](adr/0005-json-only-output.md) (JSON-only stdout) and
> [ADR 0006](adr/0006-one-shot-vs-repl.md) (one-shot, and the container it shares with MCP).

`numenews` runs one operation per invocation, prints **one JSON document** to stdout and exits. Logs
and progress go to stderr, so a command pipes straight into `jq`:

```bash
uv run numenews today | jq .dominant_number
```

Two entry points run the same application: the installed script `numenews` and
`python -m numenews.cli`.

## Prerequisites

| Command | Needs |
|---|---|
| `today` | Qdrant, an LLM endpoint, the news APIs (GDELT alone needs no key) |
| `forecast` | Qdrant and an LLM endpoint on the first read of a day |
| `history` | Qdrant |
| `search` | Qdrant |
| `patterns` | Qdrant |
| `mcp` | nothing at startup; each tool builds what it needs |

Qdrant comes from `make dev` (Docker Compose). The LLM endpoint is any OpenAI-compatible one:
`OPENAI_API_KEY`, or `OPENAI_BASE_URL` for a keyless local server (Ollama, vLLM, LM Studio) —
see [ADR 0004](adr/0004-pydantic-ai-choice.md). Embeddings are always local (`fastembed`); the two
`bge` models are downloaded on first use into `.cache/fastembed`.

```bash
uv sync --all-extras        # install, including the Typer dependency of the CLI
make dev                    # start Qdrant and wait until it is healthy
cp .env.example .env        # optional: the news keys, and your LLM endpoint
uv run numenews --version
```

## Global options

These come **before** the command name:

| Option | Meaning |
|---|---|
| `--version` | Print `{"name": "numenews", "version": "0.1.0"}` and exit. |
| `--pretty / --no-pretty` | Indent the JSON (default) or write it on one line. |
| `--help` | Click's help text. The one stdout writer that is not a command result. |

```bash
uv run numenews --no-pretty today        # one line, for logs and `jq -c`
uv run numenews --help                   # the command list
```

## Commands

| Command | Arguments | Prints | Task |
|---|---|---|---|
| [`today`](#today) | `--topic TEXT` (default `politics`) | `Forecast` | 7.3 |
| [`forecast`](#forecast) | `--date TEXT` (default `today`) | `Forecast` | 7.4 |
| [`history`](#history) | `--number INT`, `--days INT` (1–365, default 30) | `HistoryResult` | 7.5 |
| [`search`](#search) | `--query/-q TEXT`, `--collection news\|patterns`, `--limit INT` (1–50, default 10) | `CollectionQueryResult` | 7.6 |
| [`patterns`](#patterns) | `--type TEXT`, `--min-strength FLOAT` (0–1), `--limit INT` (1–200, default 50) | `PatternsResult` | 7.7 |
| [`mcp`](#mcp) | `--transport stdio` (default `stdio`) | JSON-RPC (the MCP wire) | 7.8 |

### `today`

Fetches the topic's news for the last seven days, extracts their numbers, stores what it read, and
prints the day's reading. Running it twice is cheap and idempotent: an article already in the store is
skipped before its extraction, and a day that already has a stored reading is answered from Qdrant
without a model run.

```bash
uv run numenews today
uv run numenews today --topic technology
uv run numenews today | jq '{number: .dominant_number, master: .master_active}'
```

```json
{
  "date": "2026-09-21",
  "dominant_number": 11,
  "master_active": true,
  "patterns": [
    {
      "id": "0f1d7a1e-6a7a-5f0e-9d2a-1c8b0f2a3d4e",
      "type": "repetition",
      "numbers": [11],
      "news_ids": ["b371bc46-7b4b-5b38-92db-cdf94a550f33"],
      "strength": 0.9,
      "interpretation": "Число 11 повторяется в новостях дня.",
      "discovered_at": "2026-09-21T12:00:00Z"
    }
  ],
  "forecast": "День под знаком одиннадцати.",
  "advice": "Слушайте интуицию.",
  "warnings": ["Возможны повторяющиеся события."]
}
```

The day and the window come from the pipeline's clock (UTC). `--topic` defaults to `politics` so the
bare command in the roadmap's definition of done works.

### `forecast`

Prints the reading for a day **without fetching anything**: it reads the stored seven-day window and
runs the model only when that day has no stored reading yet. This is the command for a day that is not
today.

```bash
uv run numenews forecast --date 2026-09-22
uv run numenews forecast --date tomorrow
uv run numenews forecast --date +3d
```

The printed document is the same `Forecast` shape as `today`.

The `--date` grammar is:

| Form | Meaning |
|---|---|
| `2026-09-22` | an absolute UTC day (`date.fromisoformat`, so `20260922` works too) |
| `today`, `tomorrow`, `yesterday` | relative to the day the pipeline clock reads |
| `+3d`, `-2d`, `+0d` | a whole-day offset |

Anything else is a usage error (exit code 2, nothing on stdout).

### `history`

Prints when a number was activated in the news: one entry per `(news item, number)` pair an ingest
stored, newest first, with the snippet the number was read in. `--days` ends today and includes it, so
`--days 1` is today.

```bash
uv run numenews history --number 11
uv run numenews history --number 11 --days 30
uv run numenews history --number 11 | jq '.activations | length'
```

```json
{
  "number": 11,
  "days": 30,
  "activations": [
    {
      "number": 11,
      "date": "2026-09-21",
      "news_id": "b371bc46-7b4b-5b38-92db-cdf94a550f33",
      "context": "eleven ministers resigned after the vote"
    }
  ]
}
```

### `search`

Searches the stored entities **by meaning**. `--collection news` (the default) runs the same hybrid
(multi-stage, RRF-fused) search as the MCP `query_qdrant` tool; `--collection patterns` finds saved
pattern interpretations. The query is embedded locally with `fastembed`, so no model call and no key
are involved.

```bash
uv run numenews search -q "число 7 и деньги"
uv run numenews search -q "master numbers around money" --collection patterns
uv run numenews search -q "выборы" --limit 5 | jq '.items[].title'
```

```json
{
  "collection": "news",
  "query": "число 7 и деньги",
  "items": [
    {
      "id": "5c2a1f0e-9b3d-4a6c-8e1f-2d7b9c0a4e5f",
      "title": "Seven seats lost in the vote",
      "text": "Seven seats lost in the vote body",
      "source": "example.com",
      "date": "2026-09-20",
      "url": "https://example.com/seven-seats-lost",
      "numbers": [7],
      "numerology_value": 7
    }
  ]
}
```

### `patterns`

Lists the patterns already stored — by an `analyze` step or by the MCP `save_pattern` tool — strongest
first, optionally filtered by the two indexed payload fields. Unlike `search --collection patterns`,
this is an exact question, not a similarity one.

```bash
uv run numenews patterns
uv run numenews patterns --type resonance --min-strength 0.7
uv run numenews patterns --min-strength 0.7 | jq '[.patterns[].interpretation]'
```

```json
{
  "pattern_type": "resonance",
  "min_strength": 0.7,
  "patterns": [
    {
      "id": "8bb3a3e4-53cd-5333-92ab-5309c63d3b78",
      "type": "resonance",
      "numbers": [11, 22],
      "news_ids": ["b371bc46-7b4b-5b38-92db-cdf94a550f33"],
      "strength": 0.87,
      "interpretation": "Числа 11 и 22 резонируют в новостях о технологиях.",
      "discovered_at": "2026-09-21T12:00:00Z"
    }
  ]
}
```

### `mcp`

Serves the nine MCP tools over stdio, exactly like `python -m numenews.mcp` and `make mcp`. This is the
long-running counterpart of the other commands; its stdout is the JSON-RPC wire, not a JSON document.

```bash
uv run numenews mcp
uv run numenews mcp --transport stdio
```

The tool surface is documented in [`MCP_TOOLS.md`](MCP_TOOLS.md).

## Exit codes and failures

| Code | Meaning | Streams |
|---|---|---|
| `0` | the command answered | one JSON document on stdout, logs on stderr |
| `1` | an expected domain failure | `{"error": …, "kind": …}` on stdout, the detail logged to stderr |
| `1` | a defect (anything else) | traceback on stderr, stdout empty |
| `2` | a usage error (bad flag, unknown command, bad `--date`) | message on stderr, stdout empty |

```bash
uv run numenews today; echo "exit: $?"
```

```json
{
  "error": "Qdrant health check failed (Server disconnected without sending a response.): start the server with `make dev` and check QDRANT_URL in .env",
  "kind": "VectorStoreError"
}
```

`kind` is the exception class name, which lets a script branch without parsing the message:

```bash
uv run numenews history --number 11 | jq -r '.kind // "ok"'
```

## Recipes

```bash
# the day's number
uv run numenews today | jq .dominant_number

# is a master number active today?
uv run numenews today | jq .master_active

# one compact line per run, ready for a log
uv run numenews --no-pretty today >> forecasts.jsonl

# the headlines a semantic query finds
uv run numenews search -q "финансы" | jq -r '.items[].title'

# how often a master number was active this month
uv run numenews history --number 11 --days 30 | jq '.activations | length'

# the strong patterns only
uv run numenews patterns --min-strength 0.8 | jq '.patterns[].interpretation'
```

## Relationship to the MCP tools

Both interfaces are thin wrappers over the same layers, so the mapping is direct:

| CLI | MCP tool |
|---|---|
| `today` | `fetch_news` + `find_patterns` + `build_forecast` (the pipeline chain) |
| `forecast` | `build_forecast` |
| `history` | `get_history` |
| `search` | `query_qdrant` (without the optional payload filters) |
| `patterns` | the filtered read of the `patterns` collection |
| `mcp` | serves all nine tools |

## Verification

```bash
uv run pytest tests/unit/test_cli_main.py tests/unit/test_cli_output.py tests/unit/test_cli_dates.py
uv run pytest tests/integration/test_cli.py        # every command through CliRunner
uv run numenews --version
uv run numenews --help
```

`tests/integration/test_cli.py` drives the real Typer application through `typer.testing.CliRunner`
with an in-memory Qdrant, fake embedders and scripted `pydantic-ai` agents, so no service and no model
is reached. The live form of the definition of done needs Qdrant and an LLM endpoint; with a reading
already stored for the day, `numenews today | jq .dominant_number` works against Docker Qdrant even
without a model call.
