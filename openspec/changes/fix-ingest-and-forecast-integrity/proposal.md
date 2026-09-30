# Proposal

## Why

An audit of the ingest and forecast paths found six defects that either lose stored memory or answer
from the wrong evidence. The worst is silent and permanent: ingest writes the `news` collection, the
`numbers` patterns and the `number_history` log as three separate steps, but its idempotency check
reads only the `news` collection. A run that dies partway through the write phase — a Qdrant restart,
a dropped connection, each history upsert being its own round trip — leaves those articles stored and
therefore "known", so every later run skips them and their activation history is never written.
Nothing in the public surface can repair it. The product's long-term memory degrades quietly, and
later forecasts cite incomplete evidence.

The remaining five are smaller but each is a wrong answer rather than a missing one: `forecast(day)`
derives its news window from the wall clock instead of from `day` and caches the result under `day`
forever, so `--date -3d` reads today's news; `summarize` saves a digest twice and labels the second
copy with a period the model never saw; a single malformed `Retry-After` header turns one source's
rate limit into a failed run; `dominant_number` accepts any positive integer despite documenting a
reduced-value contract; and activation snippets anchor on digit substrings, so the number `3` is
recorded as read inside `30`.

## What Changes

- **Ingest becomes crash-safe.** Re-running ingest after a partial write MUST NOT skip an article
  whose activation history or number patterns were never written. Either the three writes for one
  article complete together or the article stays eligible for re-ingest.
- **`forecast(day)` derives its window from `day`.** The news window ends on the day being read, not
  on the current UTC day, and a day with no news still falls back to `reduce_date(day)`. Both public
  callers pass the day through, so `forecast --date -3d` and `build_forecast(<past day>)` read and
  cache a reading built from that day's evidence.
- **A digest is saved once, under a period it actually covers.** The summary limit continues to bound
  the prompt only; the stored digest is not relabelled with a range the model never read, and no
  orphan digest point is left behind for a sub-period.
- **A malformed `Retry-After` is one source's failure, not the run's.** The header is parsed per the
  RFC 9110 grammar (integer seconds, or an HTTP-date), anything else falls back to exponential
  backoff, and the wait is clamped to a non-negative bound so it can never reach the retry sleep as a
  non-finite value.
- **`dominant_number` enforces the contract it documents**, rejecting values that are not reduced
  numbers instead of accepting any positive integer.
- **Activation snippets anchor on the number as a whole token**, not inside a larger number, so the
  evidence stored in the semantic index names the mention it claims.
- Two documentation defects are corrected alongside the code: the `find_date_resonances` docstring
  disagrees with its implementation about ordering, and `normalize_text`'s `casefold` expands `ß` to
  `ss`, which contradicts the gematria module's stated "unmapped characters drop out" rule.

Not in this change: the HTTP credential-at-rest leak, the RFC 9111 directive gap, and the per-activation
history round trips. They are hardening with no behaviour delta and are proposed separately as
`harden-news-cache-and-source-robustness`.

## Capabilities

### New Capabilities

- `news-memory`: what ingest must leave behind — the per-article write set that makes a re-run safe,
  the one-summary-per-period rule for digests, and the snippet rule that makes a stored activation
  name the mention it was read in.

### Modified Capabilities

- `mcp-surface`: `build_forecast` pins its news window to the day being read instead of the current
  day; `fetch_news` gains the guarantee that a malformed `Retry-After` degrades one source rather
  than failing the call.
- `cli-surface`: `forecast` derives its window from the requested day, so a past or future day is
  read from that day's evidence and the `today` window stays the current one.

## Impact

Affected code:

- `src/numenews/pipeline/steps.py` — the ingest write phase and its skip check, `forecast`'s window
  bounds, `summarize`'s second digest save, `context_snippet`'s anchoring.
- `src/numenews/pipeline/context.py` and `src/numenews/agents/summarize.py` — where a digest's period
  is derived and where it is stored.
- `src/numenews/mcp/tools.py`, `src/numenews/cli/commands.py` — passing the day through to `forecast`.
- `src/numenews/news/http.py` — `Retry-After` parsing and the retry wait.
- `src/numenews/numerology/dominant.py` — the reduced-value guard.
- `src/numenews/news/gnews.py`, `src/numenews/cli/main.py`, `src/numenews/vector/history.py` — the
  smaller robustness defects the audit's follow-up list names.

Behaviour and compatibility:

- **BREAKING** for stored data: readings already cached under a non-current day were derived from the
  wrong window. The change does not rewrite them; a follow-up re-read is required to correct an
  affected day, and the proposal deliberately leaves existing points untouched rather than deleting
  a user's stored memory.
- No public signature, argument or output shape changes. Both surfaces answer the same models with
  the same fields; only which evidence a reading is built from changes.
- No new dependency. Qdrant remains the only state store.

Verification impact:

- New integration tests for a crash injected between the ingest writes, for `forecast(past_day)`
  window provenance, and for non-numeric and negative `Retry-After` values.
- New unit tests for the `dominant_number` guard and for digit-boundary snippet anchoring.
