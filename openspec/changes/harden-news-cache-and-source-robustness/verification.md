# Verification

Recorded by tasks 4.1 and 4.2: the full gate, and the check that this change composes with
`fix-ingest-and-forecast-integrity` (already applied when this change was implemented).

## Result

`uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest tests/unit
tests/integration -v` passes, and `openspec validate "harden-news-cache-and-source-robustness"
--strict` reports the change valid. **750 passed, 8 skipped.** The skips are the
Qdrant-from-Docker checks that need `make dev` — their documented behaviour, not a gap this change
opened.

This change sets `skip_specs: true`: no requirement in `mcp-surface` or `cli-surface` describes the
storage format of the HTTP cache, the directives a response may carry, or the number of round trips
an ingest performs. Nothing these surfaces return changed, so there is no spec delta to verify.

## 4.2 — the two changes compose

The invariant `fix-ingest-and-forecast-integrity` introduced is that an ingest's write phase ends with
the `news` upsert, because an article's presence in that collection is the commit marker the
idempotency check reads. This change replaced the statement immediately before the pattern write:

```
await pipeline.run_blocking(lambda: record_activations(pipeline.store, activations))   # was a loop
await pipeline.run_blocking(lambda: upsert_number_patterns(pipeline.store, activations))
stored = await pipeline.run_blocking(lambda: upsert_news(pipeline.store, items))       # still last
```

The sequence is unchanged, so the invariant holds in either order of application: this change rewrote
one statement inside the phase and did not move, add or remove a write. The guard is behavioural
rather than textual — `tests/integration/test_pipeline_ingest.py` parametrizes over all three writes
and asserts that interrupting any one of them leaves work the next ingest completes, which fails if the
`news` upsert stops being last.

The ingest tests from both changes pass together:

```
uv run pytest tests/integration/test_pipeline_ingest.py tests/integration/test_pipeline_e2e.py \
  tests/integration/test_pipeline_forecast.py tests/integration/test_pipeline_context.py \
  tests/integration/test_mcp_tools.py -q
64 passed
```

## Deviation: design decision 1 was reversed during implementation

`design.md` first chose to redact the credential out of the stored request. That does not work, and
the plan was rewritten before the code was: `hishel` reuses an entry only when the stored request URL
equals the live one byte for byte (`IdleClient.next`, `hishel/_core/_spec.py:1173`), so a redacted URL
can never match and the entry would be written and never served — losing exactly the cache that
redaction was chosen to keep, and leaving an unusable row behind. Measured over one cache directory:
with the stored URL redacted the next identical fetch goes upstream; with it restored to the real key
the same fetch is served from the cache; redacted again, it misses again.

The mechanism became a request filter that refuses to cache a credentialed request at all, which hishel
runs before it computes a cache key — so the credential reaches neither the entry nor the key, and the
cache is lost for that source, which is the same cost the rejected alternative had. `proposal.md`,
`design.md` and tasks 1.1–1.3 were amended to match, and the reasoning is recorded durably in
[ADR 0014](../../../docs/adr/0014-cache-only-what-may-be-kept.md), which narrows
[ADR 0009](../../../docs/adr/0009-hishel-caching.md).

**The accepted cost, stated plainly:** Mediastack — the one source of the five that authenticates in
the query string — no longer gets cache hits. A repeat of the same query inside the fifteen-minute TTL
reaches the origin again, so its free-tier quota (100 calls a month) is spent faster than before. The
alternative that keeps the cache needs a dependency on hishel's private cache transport, which was
rejected. The other four sources and GDELT are unaffected, verified by
`test_a_refused_request_leaves_the_cache_working_for_the_next_one`.

## Deviation: two existing tests changed, one line each

Task 3.5 asked to confirm the existing ingest tests pass unchanged. Two did not, and could not:

- `tests/integration/test_pipeline_ingest.py:228` — the parametrized monkeypatch target
  `record_activation` → `record_activations`.
- `tests/integration/test_mcp_tools.py:541` — the same target in `_fail_the_first_write`.

Both simulate an interrupted write by patching the write function **by name** on
`numenews.pipeline.steps`, so the rename broke the patch target and the tests would otherwise have
silently stopped interrupting. No assertion, fixture or expected value changed; the stored result is
identical, and the ingest and e2e suites pass. Keeping `record_activation` imported in `steps.py`
purely to stay patchable would have been an unused import.

## Added scope

- **`docs/adr/0014-cache-only-what-may-be-kept.md`** — not named by any task, but `AGENTS.md` requires
  an ADR for an architectural decision and ADR 0001 makes ADRs immutable, so the reversal in decision 1
  and the narrowed `Cache-Control` policy needed a new record rather than an edit of ADR 0009. ADR
  0009's status now points at it; its decision text is untouched.
- **`_forbids_storing` also covers `private`** — task 2.1 names it, and design decision 2 justifies it.
- **One unit test beyond 3.3's two** (`test_a_batch_is_one_upsert_carrying_every_activation`), pinning
  the change's central claim at the call level.
- **Mutation checks.** Each new behaviour was verified to fail without its implementation: removing the
  request filter fails `test_a_request_carrying_a_credential_is_never_cached`; removing the directive
  rule fails all three `test_a_response_that_forbids_storing_is_fetched_again` cases; removing the
  Python confirmation from the leftover-credential scan fails the quiet-cache test. A test that cannot
  fail is not evidence, so this was checked rather than assumed.

## What this change does not do

- **No migration.** Rows written before it still hold the credential; removing
  `.cache/hishel/news.db` is the documented operator action, and building the client logs
  `news.http.cache_holds_credential` so it is visible.
- **No switch to `SpecificationPolicy`** and no honouring of freshness metadata: the TTL remains the
  freshness mechanism, and the three refused directives are the deliberate exception to it.
