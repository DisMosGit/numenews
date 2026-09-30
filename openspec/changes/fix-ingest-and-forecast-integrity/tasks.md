# Tasks

## 1. Make an interrupted ingest recoverable

- [x] 1.1 Reorder the ingest write phase in `src/numenews/pipeline/steps.py` so the `news` upsert is the last write, after the number patterns and the activation history, and replace the ordering comment with why `news` is the commit marker the skip check reads. Verify with `uv run ruff check . && uv run mypy .`
- [x] 1.2 Add the interruption tests to `tests/integration/test_pipeline_ingest.py`: the write phase is interrupted at each of the writes it has (the article's own point is last, so the "after the news upsert" crash point no longer exists), the next run completes the memory, and the re-run reads no article that was already complete. Verify with `uv run pytest tests/integration/test_pipeline_ingest.py -v`
- [x] 1.3 Add the same guarantee at the MCP boundary in `tests/integration/test_mcp_tools.py`: `fetch_news` followed by an interrupted ingest, then a re-run, leaves `get_history` answering the activations. Verify with `uv run pytest tests/integration/test_mcp_tools.py -v`
- [x] 1.4 Record the write order and the commit-marker rule in `docs/QDRANT_COLLECTIONS.md` next to the three collections it spans, and confirm the documented order matches the code. Verify by reading the section against `src/numenews/pipeline/steps.py`

## 2. Derive the forecast window from the day being read

- [x] 2.1 Change `forecast`'s window end in `src/numenews/pipeline/steps.py` to default to `day` instead of the clock, keep `today` as the explicit override, and align the `today` argument docstring with the window it now bounds. Verify with `uv run mypy .`
- [x] 2.2 Add the window-provenance tests to `tests/integration/test_pipeline_forecast.py`: a reading for a past day draws no item published after it and cites no activation dated after it, a reading for a future day behaves the same way, and a day whose window holds no news still answers from `reduce_date(day)`. Verify with `uv run pytest tests/integration/test_pipeline_forecast.py -v`
- [x] 2.3 Add the CLI-level test to `tests/integration/test_cli.py` for `forecast --date` naming a past day, asserting the printed reading is the one stored under that day. Verify with `uv run pytest tests/integration/test_cli.py -v`
- [x] 2.4 Document the window rule where the pipeline is described in `docs/RAG_PIPELINE.md`, and note in `docs/USER_FLOW.md` that `forecast --date` reads that day's window. Verify the wording matches the spec scenario by reading both files

## 3. Save one digest per period, labelled with the period it read

- [x] 3.1 Give `build_digest` in `src/numenews/pipeline/context.py` the intended period and item range as inputs, so it stores one digest whose period and numbers cover the older range while the prompt stays bounded by `summary_limit`. Verify with `uv run mypy .`
- [x] 3.2 Delete the second digest save and the relabelling block in `summarize` (`src/numenews/pipeline/steps.py`), leaving the summary limit to bound the prompt only. Verify with `uv run ruff check .`
- [x] 3.3 Extend `tests/unit/test_pipeline_context.py` and `tests/integration/test_pipeline_context.py` for a range longer than `summary_limit`: exactly one digest point exists, its period covers the range, and asking for a period that was never summarised answers nothing rather than a wider digest. Verify with `uv run pytest tests/unit/test_pipeline_context.py tests/integration/test_pipeline_context.py -v`
- [x] 3.4 Confirm the one-summary-per-period rule in `docs/RAG_PIPELINE.md` matches the new behaviour and that `docs/QDRANT_COLLECTIONS.md` still describes the digest point id correctly. Verify by reading both sections against `src/numenews/pipeline/context.py`

## 4. Treat an unusable retry hint as one source's failure

- [x] 4.1 Parse `Retry-After` in `src/numenews/news/http.py` as whole seconds only, clamp the result to `[0, _MAX_RETRY_WAIT_SECONDS]`, and fall back to exponential backoff for anything else including an HTTP-date; update the docstring to state the grammar. Verify with `uv run mypy .`
- [x] 4.2 Add the parsing tests to `tests/integration/test_news_http.py` for `nan`, a negative value, a fractional value and an HTTP-date, each asserting the error carries no retry hint and the fetch still completes. Verify with `uv run pytest tests/integration/test_news_http.py -v`
- [x] 4.3 Make GNews' 403-to-rate-limit translation reachable by the retry loop in `src/numenews/news/gnews.py` by mapping the status inside `get_response`, so the failure is classified before the retry decision rather than after it. Verify with `uv run pytest tests/integration/test_news_gnews.py -v`
- [x] 4.4 Extend `tests/unit/test_news_aggregator.py` with the degradation case: one source answering a rate limit with an unusable hint leaves the other sources' items in the combined result. Verify with `uv run pytest tests/unit/test_news_aggregator.py -v`
- [x] 4.5 Note the accepted retry-hint grammar and the backoff fallback in `docs/NEWS_SOURCES.md`, and adjust the 2.5-second value in `tests/unit/test_news_protocol.py` if it asserts a hint the parser now rejects. Verify with `uv run pytest tests/unit/test_news_protocol.py -v`

## 5. Enforce the reduced-value contract of the dominant number

- [x] 5.1 Replace the `value < 1` guard in `src/numenews/numerology/dominant.py` with membership in `REDUCED_NUMBERS`, keeping `0` rejected. Verify with `uv run mypy .`
- [x] 5.2 Add the guard tests to `tests/unit/test_dominant.py` for an unreduced value such as `15`, for a negative value, and for the empty set still answering the `0` sentinel. Verify with `uv run pytest tests/unit/test_dominant.py -v`
- [x] 5.3 State the reduced-values-only input rule in `docs/NUMEROLOGY.md` where the dominant rule is explained. Verify the documented rule matches the guard in `src/numenews/numerology/dominant.py`

## 6. Anchor an activation snippet on a whole number

- [x] 6.1 Match the number with a digit-boundary pattern in `context_snippet` (`src/numenews/pipeline/steps.py`), anchoring on the first whole-number occurrence and keeping the opening-of-text fallback when there is none. Verify with `uv run mypy .`
- [x] 6.2 Add the anchoring tests to `tests/unit/test_pipeline_ingest.py`: `3` in a text that also contains `30` anchors at the standalone `3`, a number only present inside a larger number falls back to the opening, and a decimal such as `3.5` does not anchor `3`. Verify with `uv run pytest tests/unit/test_pipeline_ingest.py -v`
- [x] 6.3 Extend `tests/integration/test_pipeline_context.py` so the snippet stored for an activation is the one the semantic `numbers` index carries. Verify with `uv run pytest tests/integration/test_pipeline_context.py -v`

## 7. Close the smaller contract-drift defects

- [x] 7.1 Correct the `find_date_resonances` docstring in `src/numenews/numerology/resonance.py` so its stated pair order matches the input order the implementation reports. Verify with `uv run pytest tests/unit/test_resonance.py -v`
- [x] 7.2 Make the gematria module docstring state that case folding is applied before the letter filter, so `ß` expanding to `ss` is documented rather than contradicting the "drops out" rule. Verify by reading `src/numenews/numerology/gematria.py` against the `ß` test in `tests/unit/test_gematria.py`
- [x] 7.3 Translate a malformed stored payload in `_scroll` (`src/numenews/vector/history.py`) into the documented `VectorStoreError` instead of letting a raw validation error escape. Verify with `uv run pytest tests/unit/test_vector_history.py tests/integration/test_vector_history.py -v`
- [x] 7.4 Stop `run_command`'s cleanup in `src/numenews/cli/main.py` from masking the original failure when closing the context itself raises, and add the regression test to `tests/unit/test_cli_main.py`. Verify with `uv run pytest tests/unit/test_cli_main.py -v`

## 8. Integration verification

- [ ] 8.1 Run the full suite and the strict validator: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest tests/unit tests/integration -v` and `openspec validate "fix-ingest-and-forecast-integrity" --strict`
- [ ] 8.2 Re-read `proposal.md`'s Impact list against the diff and confirm every named file was either changed or consciously left alone, recording any deviation in the change before archiving
