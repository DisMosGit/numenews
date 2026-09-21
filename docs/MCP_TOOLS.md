# MCP tools

`numenews` exposes nine tools over the Model Context Protocol. This document is the contract of that
surface: what each tool takes, what it returns, what it needs to be running, and how a client
connects.

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

Embeddings are always local (`fastembed`), and the news HTTP client is cached (`hishel`) for the life
of the server.

## Tools

| Tool | Arguments | Returns | Task |
|---|---|---|---|
| [`fetch_news`](#fetch_news) | `topic`, `date_range` | `list[NewsItem]` | 6.2 |
| [`extract_numbers`](#extract_numbers) | `text` | `ExtractedNumbers` | 6.3 |
| [`compute_numerology`](#compute_numerology) | `text` | `NumerologyResult` | 6.4 |
| [`find_patterns`](#find_patterns) | `news_ids` | `list[Pattern]` | 6.5 |
| [`check_master_numbers`](#check_master_numbers) | `numbers` | `MasterCheckResult` | 6.6 |
| [`build_forecast`](#build_forecast) | `day` | `Forecast` | 6.7 |
| [`query_qdrant`](#query_qdrant) | `collection`, `query`, `filters`, `limit` | `CollectionQueryResult` | 6.8 |
| [`save_pattern`](#save_pattern) | `pattern` | `Pattern` | 6.9 |
| [`get_history`](#get_history) | `number`, `days` | `list[NumberActivation]` | 6.10 |

Lists of models are wrapped by the SDK as `{"result": [...]}`; a single model is returned unwrapped.

### `fetch_news`

```python
async def fetch_news(topic: str, date_range: DateRangeInput) -> list[NewsItem]
```

Fetches the news of a topic in an inclusive date range from every configured source. The five feeds
run in parallel, a failing source is skipped with a warning, the result is de-duplicated on
`(title, source, date)` and filtered to the range.

```json
{
  "topic": "politics",
  "date_range": {"start": "2026-09-15", "end": "2026-09-21"}
}
```

```json
{
  "result": [
    {
      "id": "af8c2f10-abf5-4780-b3d7-76a14bbe3fbd",
      "title": "11th hour deal reached on the budget",
      "text": "11th hour deal reached on the budget",
      "source": "example.com",
      "date": "2026-09-21",
      "url": "https://www.example.com/politics/11th-hour-deal",
      "numbers": [11],
      "numerology_value": 11
    }
  ]
}
```

A reversed range (`start` after `end`) is refused before the sources are queried.

### `extract_numbers`

```python
async def extract_numbers(text: str) -> ExtractedNumbers
```

Reads the numbers, dates and symbols out of one text with the extraction agent. The model's reading
is combined with the deterministic regex pass, so a number written as a word is still found; a model
that cannot answer at all degrades to the regex reading. `sources` says which strategies contributed
(`"llm"`, `"regex"`).

```json
{"text": "The 11th hour deal was signed at 7"}
```

```json
{
  "numbers": [7, 11],
  "sources": ["llm", "regex"],
  "symbols": []
}
```

### `compute_numerology`

```python
def compute_numerology(text: str) -> NumerologyResult
```

Reduces a text to its numerological value: the raw gematria sum, the digit-reduced value (11, 22 and
33 are master numbers and stop there) and the rendered steps. Pure logic — no Qdrant, no model, no
configuration.

```json
{"text": "sun"}
```

```json
{
  "text": "sun",
  "gematria": 54,
  "value": 9,
  "is_master": false,
  "breakdown": ["gematria_simple = 54", "54 -> 5+4 = 9"]
}
```

### `find_patterns`

```python
async def find_patterns(news_ids: list[UUID]) -> list[Pattern]
```

Finds the connections among the stored news items with these ids, saves them and returns them. The
ids come from an earlier `fetch_news`/ingest run or from `query_qdrant`; an id that is not in the
store is skipped, and an empty list answers `[]` without asking the model. Each returned pattern
carries the `discovered_at` timestamp `save_pattern` stamped.

```json
{"news_ids": ["af8c2f10-abf5-4780-b3d7-76a14bbe3fbd"]}
```

The result is a `{"result": [Pattern, …]}` list; each pattern is
`{"id", "type", "numbers", "news_ids", "strength", "interpretation", "discovered_at"}`.

### `check_master_numbers`

```python
def check_master_numbers(numbers: list[int]) -> MasterCheckResult
```

Reports the master numbers (11, 22, 33) among a list. `master_numbers` holds the distinct values
found, ascending; `count` counts every occurrence.

```json
{"numbers": [11, 11, 7]}
```

```json
{"has_master": true, "master_numbers": [11], "count": 2}
```

### `build_forecast`

```python
async def build_forecast(day: date) -> Forecast
```

Returns the numerological reading for a calendar day and saves it. A day already read answers from
Qdrant without running a model; otherwise the reading is assembled from the last seven days of stored
news (dominant number, whether a master number is active, the patterns among them) plus the recent
activations of exactly those numbers.

```json
{"day": "2026-09-21"}
```

```json
{
  "date": "2026-09-21",
  "dominant_number": 11,
  "master_active": true,
  "patterns": [],
  "forecast": "День под знаком одиннадцати.",
  "advice": "Слушайте интуицию.",
  "warnings": ["Возможны повторяющиеся события."]
}
```

### `query_qdrant`

```python
async def query_qdrant(
    collection: Literal["news", "patterns"],
    query: str,
    filters: NewsFilterInput | None = None,   # news only
    limit: int = 10,                          # 1..50
) -> CollectionQueryResult
```

Searches the stored news (`hybrid_search_news`, with the payload filter applied inside the prefetch)
or the saved patterns (`find_similar_patterns`) by meaning. `filters` narrow by publication window,
source, reduced value or master number, and are **refused** for `patterns` rather than ignored.

```json
{
  "collection": "news",
  "query": "budget deal",
  "filters": {"date_from": "2026-09-15", "numerology_value": 11},
  "limit": 5
}
```

```json
{
  "collection": "news",
  "query": "budget deal",
  "items": [
    {"id": "af8c2f10-abf5-4780-b3d7-76a14bbe3fbd", "title": "11th hour deal reached on the budget"}
  ]
}
```

The two collections are the ones the vector layer has semantic read paths for. `number_history` is
read exactly by `get_history`; `numbers`, `forecasts` and `digests` are written but not yet
searchable.

### `save_pattern`

```python
async def save_pattern(pattern: PatternInput) -> Pattern
```

Stores one pattern and returns it as written, with `discovered_at` filled in when it was omitted.
Re-saving the same pattern id overwrites the point instead of adding a copy, and an existing
timestamp is never rewritten.

```json
{
  "pattern": {
    "id": "8f14e45f-ceea-467a-9a4f-52b3b7a0b1c2",
    "type": "repetition",
    "numbers": [11],
    "news_ids": ["af8c2f10-abf5-4780-b3d7-76a14bbe3fbd"],
    "strength": 0.9,
    "interpretation": "Число 11 повторяется в новостях недели."
  }
}
```

The returned pattern is the same object plus a `discovered_at`; `strength` must be between 0 and 1
and `type` one of `resonance`, `repetition`, `master`, `symbol`, `hidden`.

### `get_history`

```python
async def get_history(number: int, days: int = 30) -> list[NumberActivation]
```

Returns when a number was activated in the news, newest first, inside the last `days` days (the
window ends today and includes it; 1–365). One entry per `(news item, number)` pair the ingest
stored; `numerology_value` is the item's own reduced value (phase 8.1) and is absent when it has
none. The per-day frequency of the same rows is reported by `numenews history` (phase 8.2), not by
this tool: its return type is the rows themselves.

```json
{"number": 11, "days": 30}
```

```json
{
  "result": [
    {
      "number": 11,
      "date": "2026-09-21",
      "news_id": "af8c2f10-abf5-4780-b3d7-76a14bbe3fbd",
      "context": "11th hour deal reached on the budget",
      "numerology_value": 11
    }
  ]
}
```

## Failures

Two kinds of failure are possible, and the SDK reports them differently:

- **A tool error** (`is_error: true`, no `structuredContent`): an expected condition the model can
  correct. The message is the layer's own, e.g. `collection 'news' does not exist: call
  VectorStore.ensure_collections() first`, `qdrant is not reachable …start the server with make dev`,
  `No LLM endpoint configured: set OPENAI_API_KEY …`, `no news sources are configured …`, or
  `filters apply to the news collection only`.
- **A rejected argument** (also `is_error: true`): the SDK validates arguments against the published
  schema before the body runs, so a malformed UUID, an unknown `collection`, a reversed `date_range`,
  a `strength` above 1 or `days: 0` come back with the offending field named.
- **Anything else** is a bug in this project and is deliberately *not* translated: the SDK returns a
  generic "Error executing tool" and logs the traceback to stderr.

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
make mcp                                            # the server, waiting on stdin
uv run python -m numenews.mcp                       # the same, by module
uv run pytest tests/integration/test_mcp_stdio.py   # the same handshake, as a test
```

`tests/integration/test_mcp_stdio.py` is the automated stand-in for the roadmap's manual
"open it in Claude Desktop" check.
