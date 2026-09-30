# Verification

Recorded by task 8.2: `proposal.md`'s Impact list re-read against the diff that implements the
change, so every file it names is either changed or consciously left alone.

## Result

`uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest tests/unit
tests/integration -v` passes, and `openspec validate "fix-ingest-and-forecast-integrity" --strict`
reports the change valid. 708 passed, 8 skipped — the skips are the Qdrant-from-Docker checks that
need `make dev`, which is their documented behaviour, not a gap this change opened.

## Affected code, file by file

| File named by the proposal | Outcome |
|---|---|
| `src/numenews/pipeline/steps.py` | Changed: the ingest write phase, `forecast`'s window bounds, `context_snippet`'s anchoring |
| `src/numenews/pipeline/context.py` | Changed: `build_digest` takes the period and numbers it stores |
| `src/numenews/news/http.py` | Changed: `_retry_after_seconds`' grammar and clamp, `rate_limit_statuses` |
| `src/numenews/numerology/dominant.py` | Changed: the reduced-value guard |
| `src/numenews/news/gnews.py` | Changed: the 403 is named as a rate limit during the request |
| `src/numenews/vector/history.py` | Changed: `_scroll` translates a malformed payload |
| `src/numenews/cli/main.py` | Changed: `run_command`'s cleanup no longer masks the body's failure |

## Deviation: three named files were not changed

Three files the proposal's Impact list names are untouched by the diff, because the defect each was
listed for is fixed elsewhere. None of them narrows specified behaviour: in every case the observable
contract in the spec deltas is implemented and covered by a test.

1. **`src/numenews/agents/summarize.py`** — named under "where a digest's period is derived and where
   it is stored". `SummarizeAgent.summarize` still derives a period from the items it was handed, and
   that stays correct: it labels the *draft* it returns. The change is that `build_digest` now
   overwrites that draft's period and numbers with the period the caller states (design decision 3),
   so the responsibility for "what the digest covers" moved to the pipeline layer rather than into
   the agent. The agent's own contract — and its tests in `tests/unit/test_agents_summarize.py` — are
   unchanged, which is what the spec requires: `news-memory` speaks about the *stored* digest.
2. **`src/numenews/mcp/tools.py`** — named under "passing the day through to `forecast`". No change
   was needed: `build_forecast` already calls `pipeline.forecast(day)` with the day alone, and design
   decision 2 deliberately puts the correct behaviour in `forecast`'s default rather than at the two
   call sites that exist today ("wrong at the third one added later"). The spec scenario is verified
   at the pipeline level instead, in `tests/integration/test_pipeline_forecast.py`, which is where
   the window is actually derived.
3. **`src/numenews/cli/commands.py`** — named for the same reason. `commands.forecast` resolves
   `--date` and delegates to `pipeline.forecast(day)`; the window fix is the default it inherits. The
   CLI-level consequence is covered by
   `tests/integration/test_cli.py::test_forecast_reads_a_past_day_from_its_own_window`, which is the
   test task 2.3 asked for.

The design's Open Questions already flagged that the `today` parameter's job was to be an override
rather than a requirement, so leaving both callers alone is the decision the design recorded, not a
task that was skipped.

## Where the change's own spec deltas are verified

| Requirement | Test |
|---|---|
| `news-memory`: a repeated ingest never skips an incomplete article | `tests/integration/test_pipeline_ingest.py`, `tests/integration/test_mcp_tools.py` |
| `news-memory`: one digest exists per period and covers the period it states | `tests/unit/test_pipeline_context.py`, `tests/integration/test_pipeline_context.py` |
| `news-memory`: a stored activation names the mention it was read in | `tests/unit/test_pipeline_ingest.py`, `tests/integration/test_pipeline_context.py` |
| `news-memory`: the dominant number is read only from reduced values | `tests/unit/test_dominant.py` |
| `mcp-surface`: `fetch_news` degrades one source, unusable retry hint included | `tests/unit/test_news_aggregator.py`, `tests/integration/test_news_http.py`, `tests/integration/test_news_gnews.py` |
| `mcp-surface`: `build_forecast` is idempotent per day and derives its window from that day | `tests/integration/test_pipeline_forecast.py` |
| `cli-surface`: `forecast` reads a day without fetching news, from that day's window | `tests/integration/test_cli.py` |
