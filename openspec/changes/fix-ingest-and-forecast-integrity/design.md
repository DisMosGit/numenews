# Design

## Context

See `proposal.md` — Why. Three constraints from the current implementation shape every decision here.

**The write path is already idempotent per point.** `news_point_id` is the URL-derived `NewsId`,
`activation_point_id` is `uuid5(NewsId, number)`, and both are written with `wait=True`. Re-writing a
point that already exists overwrites it rather than duplicating it. So the defect is not that writes
cannot be repeated — it is that the *skip check* reads only one of the three collections.

**The skip check is the commit marker.** `ingest` decides what is fresh by asking which of the fetched
items already have a `news` point (`steps.py:211-215`). Whatever write happens last is therefore the
one that commits the article, and today that is `upsert_news`.

**`forecast` has one window-bound parameter and two callers that never set it.** `forecast(day, *,
today=None)` derives `end` from `today` or the clock, and both `build_forecast` (`mcp/tools.py`) and
the CLI `forecast` (`cli/commands.py`) call it with the day alone.

## Goals / Non-Goals

**Goals:**

- An interrupted ingest leaves the store in a state the next ingest completes on its own, with no
  operator action and no repair command.
- The commit marker and the skip check name the same collection, and that fact is obvious from the
  code rather than implied by write ordering.
- A reading for any day is derived from that day's window, on both surfaces, and a day with no news
  still answers.
- The four smaller defects are fixed where they live, each covered by the test that would have
  caught it.

**Non-Goals:**

- No new collection, no per-item marker point, no repair or force-reingest command. Adding a
  fourth collection to express "this article is complete" buys an atomicity primitive that Qdrant
  does not offer; ordering the existing writes buys the same guarantee for free.
- No transaction or rollback protocol. Qdrant has no multi-collection transaction, and the design
  does not pretend otherwise: it makes interruption *recoverable* instead of *impossible*.
- No rewrite or invalidation of readings already cached under a non-current day (see Risks).
- No change to the public tool or command surface, argument names, defaults or output shapes.

## Decisions

### 1. Order the writes so `news` is the commit marker

The write phase becomes: `number_history` first, then `numbers`, then `news` last. Each write stays a
single batch (`upsert_number_patterns` already batches; history gains a batched counterpart in the
hardening change, and until then the ordering alone closes the hole).

Why this works: a crash before the final `upsert_news` leaves the article with no `news` point, so
the next ingest sees it as fresh and re-runs it. Every write it repeats is an idempotent overwrite.
A crash after the final write cannot happen in a state where memory is incomplete, because the final
write is only reached once both other writes returned.

Alternatives considered:

- **Per-item completion marker written last.** A fourth record per article. Rejected: it encodes the
  same invariant in a second place that can itself drift out of sync, and it needs its own cleanup
  and migration story.
- **Check activation points in the skip rule.** Ask whether an article's activations exist before
  skipping it. Rejected: `numbers` and `number_history` are two collections with different purposes,
  so "complete" becomes a two-collection existence query per item on the hot path of every ingest.
  The ordering makes the same information available in the query that already runs.
- **Write the article first and track completeness separately.** Rejected for the same reason as the
  marker, plus it puts news — the item most other tools read — in a state where it exists but its
  memory does not, which is exactly the failure being fixed.

Trade-off accepted: a crash before the commit means the model runs again for those articles on the
next ingest. That is wasted compute, not lost data, and it is the correct direction to fail.

### 2. `forecast` defaults its window end to the day being read

`end` becomes `today if today is not None else day`. The `today` parameter keeps its current meaning —
an explicit override for a caller replaying a batch — but its default stops being "now". Both public
callers already pass only the day, so they need no change to become correct; the fix is in the default
and in the two docstrings that already describe the intended window (`steps.py:316-317`,
`pipeline.py:66`).

Alternatives considered:

- **Pass `today=day` from both callers.** Correct at the two call sites that exist today and wrong at
  the third one added later. Rejected: the safe behaviour belongs in the default, since the parameter
  is an override, not a requirement.
- **Remove `today` entirely.** Rejected: `summarize` and the replay paths use the same shape, and an
  explicit override stays useful for a caller summarising a fixed batch.

Consequence for `_day_history(..., today=end)`: history now ends on the day being read too, so a past
day's reading can no longer cite activations dated after it. That is the intended provenance and is
what the spec scenario asserts.

### 3. A digest is saved once, from an explicit period

`build_digest` gains the intended period and the full older range as inputs: the summariser is shown
`older[:summary_limit]`, while the stored `Digest` carries the period and numbers of the whole older
range. The second save inside `summarize` is deleted.

The split of responsibility: the *prompt* is bounded by `summary_limit`, the *stored period* is not.
`numbers` stays derived from the full older range, matching the field's documented meaning — "the
reduced values the period was read under" (`models/results.py:72-74`) — rather than from the prompt
subset.

Alternatives considered:

- **Label the digest with the subset period it actually read** (keep `build_digest`'s current save,
  delete the relabel). Honest about the prompt, but then the stored memory covers only the newest
  `summary_limit` items of the older range and the rest are covered by no digest at all — a silent
  coverage hole replacing a silent overclaim.
- **Make the limit bound the period** by partitioning the older range into several digests. Rejected
  as a larger change than the defect: it multiplies stored points and changes what `get_digest`
  answers for a period. Worth its own change if coverage per period ever matters.

### 4. `Retry-After` is parsed to the RFC 9110 grammar, clamped, and never trusted

Parse as an integer number of seconds only, clamp to `[0, _MAX_RETRY_WAIT_SECONDS]`, and return `None`
— falling through to exponential backoff — for anything else, including an HTTP-date. An HTTP-date is
valid per the RFC; converting it to a wait is not worth the code, and the existing comment already
treats the backoff as an acceptable stand-in for that branch.

The clamp is the load-bearing part: it is what makes a non-finite or negative value unable to reach
`tenacity`'s sleep, where `ValueError: Invalid delay` escapes the `NewsSourceError` hierarchy and the
aggregator re-raises it, failing the whole fetch. Rejecting the value at parse time is better than
guarding at sleep time because it keeps the invariant "a retry hint is a finite non-negative wait"
true at the point the value enters the system.

### 5. `dominant_number` validates against `REDUCED_NUMBERS`

Replace the `value < 1` guard with membership in `numerology.constants.REDUCED_NUMBERS`. The docstring
already promises rejection; the implementation was narrower than the promise. `0` stays rejected as
part of the same check, so the sentinel keeps its meaning.

### 6. The snippet anchors on a whole-number occurrence

Match the number with a digit-boundary pattern (`(?<!\d)<number>(?!\d)`) and anchor on the first
whole-number occurrence. The boundary form rather than a token-boundary form (`\b`) because `\b`
treats a decimal point as a boundary, so `3` in `3.5` would match. When no whole-number occurrence
exists, fall back to the opening of the text — the existing fallback, kept as the documented
behaviour in the `news-memory` spec.

## Risks / Trade-offs

- **Stored readings under a non-current day were built from the wrong window.** → They stay as they
  are. Deleting or recomputing a user's stored memory is a bigger, irreversible action than the bug,
  and the proposal records the re-read as the remedy. A follow-up may add an explicit invalidation
  path; it is not in this change.
- **The reordering means a crash re-runs the extraction model.** → Accepted; see Decision 1. The
  alternative — silently losing memory — is the defect.
- **`news` is briefly absent while its history exists**, so `get_history` can show an activation whose
  article is not yet stored for the duration of one run. → It is a window inside a single ingest, the
  next run repairs it, and every reader of `news` treats a missing point as "not stored" already.
- **The digest period now extends past the prompt subset**, so a period can be labelled from items the
  model did not see. → The `numbers` field and the period describe the period; the summary describes
  what was read. That split matches the field docs but is a judgement call worth reviewing: if a
  reader expects `summary` to be exhaustive over the period, the alternative in Decision 3 is the
  honest one.
- **A stricter `dominant_number` can raise where callers previously got a value.** → All current
  callers pass `numerology_value`, which is reduced by construction, so the change turns a latent
  contract violation into a loud failure rather than altering a working path.

## Migration Plan

No data migration and no configuration change. The fixes take effect on the next ingest and the next
uncached forecast. Rolling back is reverting the change: no stored shape, point id or collection
schema changes, so a store written by the fixed code is readable by the old code and vice versa.

## Open Questions

None blocking. The `numbers`-from-full-range choice in Decision 3 is the one judgement call a reviewer
may want to overturn; it does not change the approach or the task breakdown.
