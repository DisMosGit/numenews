# Choosing an MCP tool

> Phase 6. `ROADMAP.md` is the authoritative status; [`MCP_TOOLS.md`](MCP_TOOLS.md) is the contract of
> each tool (arguments, returns, failures). This document is the *selection* layer on top of it: given
> a question in prose, which of the nine tools should a model call, in what order, and what does it
> need running first.

The tools are deliberately small and orthogonal. A model chooses well when it picks the narrowest
tool that can answer, chains tools instead of guessing, and lets the tool's error message correct the
next attempt. The server's tool descriptions carry the same table; the schemas enforce the types.

## By question

| The user asks | Call | Notes |
|---|---|---|
| "What is the numerological value of *this text*?" | `compute_numerology(text)` | pure logic, needs nothing; works for a single word or a headline |
| "Which numbers are in this text?" | `extract_numbers(text)` | the LLM reading plus the regex pass; needs an LLM endpoint |
| "Are 11/22/33 in this list?" | `check_master_numbers(numbers)` | pure logic, needs nothing |
| "What was in the news about X?" | `fetch_news(topic, date_range)` | **fetches, does not store**; for stored news use `query_qdrant` |
| "What did we store about X?" | `query_qdrant(collection="news", query=…)` | semantic search over what an ingest already wrote |
| "Which saved patterns resemble this?" | `query_qdrant(collection="patterns", query=…)` | `filters` are refused for `patterns` |
| "What connects these articles?" | `find_patterns(news_ids)` | ids from `fetch_news` or `query_qdrant`; saves what it finds |
| "Remember this pattern" | `save_pattern(pattern)` | needs a stable `id`; re-saving overwrites |
| "What is the reading for this day?" | `build_forecast(day)` | stored day answers without a model |
| "When was 11 active?" | `get_history(number, days)` | exact rows, newest first; Qdrant only |

## The canonical chains

**Ingest-and-read a topic.** `fetch_news` → `find_patterns` → `build_forecast` — the same order the
`numenews today` command runs, except that the CLI's pipeline also *stores* the articles it fetches.
`fetch_news` alone returns them; to make them searchable and to grow `number_history`, use the CLI
(`numenews today`) or `Pipeline.ingest`, because there is no MCP tool that ingests.

**Read what is already there.** `query_qdrant(collection="news", query=…)` → `find_patterns(news_ids)`
→ `build_forecast(day)` — the retrieval path, with no news API involved.

**Explain a text.** `extract_numbers(text)` → `check_master_numbers(numbers)` → `compute_numerology(text)`
— all three are cheap and independent; there is no tool that does them together on purpose, so a
model can stop as soon as it has the answer.

**Ask about a number over time.** `get_history(number)` — one call; the per-day aggregation is
`numenews history` (CLI), not this tool.

## What each call needs to be running

| Group | Tools | Prerequisite |
|---|---|---|
| Pure | `compute_numerology`, `check_master_numbers` | nothing |
| Model | `extract_numbers` | an LLM endpoint |
| Model **and** storage | `find_patterns`, `build_forecast` | Qdrant and an LLM endpoint |
| Network | `fetch_news` | the news APIs (GDELT alone needs no key) |
| Storage | `query_qdrant`, `save_pattern`, `get_history` | Qdrant (`make dev`) |

Nothing is connected at startup. A missing prerequisite comes back as a tool error naming the fix
(`set OPENAI_API_KEY`, `start the server with make dev`), which is the model's cue to change plan or
report the limitation — not to retry the same call.

## When to use the CLI instead

| Situation | Interface |
|---|---|
| A single machine-readable answer for a script or a cron job | CLI (`numenews search|history|patterns|today|forecast`) |
| Fetching **and storing** a window, growing history | CLI (`numenews today`) or a direct `Pipeline` call |
| An interactive conversation that decides what to ask next | MCP |
| A host that should expose the domain to an assistant | MCP |

The two share one `AppContext`, so they build the store, the agents and the cached news client the
same way. Neither is a superset: the CLI owns the pipeline commands and the `by_day` history
aggregation; MCP owns the incremental tool surface.

## How the model is steered

- **Descriptions name the boundary.** "Fetch" versus "search what is stored", "the day's reading"
  versus "the activation rows" — the distinction is in the tool text, because a model that confuses
  them produces a plausible but wrong answer.
- **Schemas refuse rather than guess.** A reversed `date_range`, a `strength` above 1, a `days: 0`
  and a `filters` argument on `patterns` all come back as a rejected argument with the field named.
- **Empty is an answer.** `find_patterns([])` is `[]`, not an error; an unknown `news_id` is skipped.
  A model should report "nothing found", not retry.
- **Reading is idempotent.** `build_forecast` for a day already read serves the stored reading; a
  second `save_pattern` with the same id overwrites. A retry after a timeout is therefore safe.
- **`query_qdrant` is the only search surface.** `numbers`, `forecasts` and `digests` are written but
  not yet semantically searchable; `get_history` is the exact read for `number_history`. Asking for a
  collection outside `news`/`patterns` is rejected.

## Anti-patterns

- Calling `fetch_news` and then `find_patterns` on the *ids it returned* expecting the articles to be
  stored — `fetch_news` does not write to Qdrant. Ingest first (CLI), then search.
- Calling `build_forecast` for a day whose window has no stored news and presenting the derived
  reading as if it were evidence-based; the reading falls back to `reduce_date(day)`, which the
  returned fields make visible.
- Passing `filters` to a `patterns` query, or asking `query_qdrant` for `number_history`.
- Treating a tool error as a transient failure and retrying unchanged — the errors are actionable by
  design (not configured, not reachable, wrong argument).
- Asking for all nine tools at once instead of the two or three the question needs.

## See also

- [`MCP_TOOLS.md`](MCP_TOOLS.md) — the exact arguments and JSON of every tool
- [`USER_FLOW.md`](USER_FLOW.md) — the CLI commands and their JSON
- [`CONTEXT_MANAGEMENT.md`](CONTEXT_MANAGEMENT.md) — what a forecast's window and memory actually are
