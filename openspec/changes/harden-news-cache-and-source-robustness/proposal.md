# Proposal

## Why

Three hardening items from the same audit that produced `fix-ingest-and-forecast-integrity`. None of
them changes what the project answers, which is why they are a separate change: they change what the
project leaves at rest, which requests it makes, and how much work one ingest does.

The security one is the reason this is not merely tidy-up. Mediastack authenticates by putting
`access_key` in the query string, and the shared HTTP cache persists the full request URL — the whole
query string — in an unencrypted sqlite database at `.cache/hishel/news.db`. With `MEDIASTACK_KEY`
configured, the secret sits in cleartext on disk, where a backup, a shared machine or a copied
checkout exposes it. The cache's own TTL does not remove rows promptly. The module already takes care
not to log the query string; it simply does not apply the same care to what it stores.

The other two are correctness-of-behaviour rather than correctness-of-answer. The cache runs hishel's
`FilterPolicy`, which applies only the filters handed to it, so a response carrying `Cache-Control:
no-store` or `no-cache` is stored and replayed for the whole TTL without revalidation — a deviation
from RFC 9111 MUST-level clauses that is deliberate for vendor responses lacking freshness headers but
broader than the vendors require. And ingest writes activation history one point per round trip,
re-creating the collection on every call, so an ingest with hundreds of activations performs hundreds
of redundant round trips and holds the interruption window open for as long as it can.

## What Changes

- **The HTTP cache stores no credential.** A request whose query string carries a credential is
  persisted with that parameter's value replaced by a fixed placeholder. The request that leaves the
  process is unchanged, the cache key is unchanged, and the credential never reaches the database.
- **The cache honours the directive that forbids storing.** A response carrying `Cache-Control`
  `no-store` or `no-cache` is not stored, so it cannot be replayed within the TTL without
  revalidation, joining the existing rule that error responses are not stored.
- **Activation history is written as one batch**, with the collection ensured once per ingest instead
  of once per activation. The stored result is identical: one point per `(article, number)` pair, and
  a repeated ingest still overwrites rather than duplicates.

Not in this change: everything in `fix-ingest-and-forecast-integrity`. The write-order fix that makes
an interrupted ingest recoverable lands there; this change narrows the same window from the other
side by making the history write one call instead of N.

## Capabilities

### New Capabilities

None. No requirement in `mcp-surface` or `cli-surface` describes the storage format of the HTTP
cache, the directives a response may carry, or the number of round trips an ingest performs. The
externally visible answers of both surfaces are unchanged, so no spec delta applies and this change
sets `skip_specs: true` in `.openspec.yaml`. The behaviour that *is* spec-level — that a source
failure degrades one source instead of the run — belongs to the retry-hint fix and is specified there.

### Modified Capabilities

None.

## Impact

Affected code:

- `src/numenews/news/http.py` — the storage wrapper that redacts a request before it is written, and
  `_CacheOnlySuccesses`, widened to refuse a response the origin forbade storing.
- `src/numenews/vector/history.py` — a batched history write alongside the single-activation one.
- `src/numenews/pipeline/steps.py` — the ingest write phase calls the batched write once.

Behaviour and compatibility:

- No public signature, argument, default or output shape changes; no new dependency. The storage
  wrapper sits between the client and `AsyncSqliteStorage`, which it delegates to.
- **A one-time privacy action:** cache rows written before this change still hold the credential. The
  change does not delete them, because deleting the cache is the operator's call; `docs/NEWS_SOURCES.md`
  documents the one-line removal of `.cache/hishel/news.db` and the fact that the cache is disposable.
- Honouring `no-store`/`no-cache` means those responses are fetched again within the TTL, so request
  volume against the free-tier quotas can rise. This is the trade-off the change accepts knowingly:
  the cache exists to spare the quotas, and an origin that forbids storing is not the case it was
  built for. The TTL remains the mechanism for every response that does not forbid storing.

Verification impact:

- New integration tests assert a credentialed request is absent from the database after a cached
  fetch, that a `no-store` response is not replayed, and that the batched write stores exactly the
  points the per-row loop stored.
