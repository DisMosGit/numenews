# Design

## Context

See `proposal.md` — Why. Three facts about the current implementation decide the approach.

**hishel's filter path never looks at directives.** `build_news_client` (`news/http.py:99-109`) passes
`FilterPolicy(response_filters=[_CacheOnlySuccesses()])`. `FilterPolicy` applies only the filters it
is given; the RFC 9111 directive handling lives in `SpecificationPolicy` and is never reached. So
`_CacheOnlySuccesses` is the whole storage decision, and freshness comes only from the storage's
`default_ttl` (`NEWS_CACHE_TTL_SECONDS`).

**A request filter runs before the cache key is computed, and can bypass the cache.** In
`hishel._async_cache._handle_request_with_filters`, request filters run first; returning `False` sends
the request straight upstream without looking in the cache, without computing a key and without
writing anything. A filter is not a redaction hook, but it is the whole mechanism this change needs.

**A stored entry is reused only when its request URL matches the live one exactly.** Both reuse paths
compare them literally: `IdleClient.next` (`hishel/_core/_spec.py`) drops any entry whose
`request.url` differs, and the filter path repeats the same comparison before serving one. This is the
fact that decided decision 1 — a redacted URL can never equal the live one, so an entry written that
way would be stored and then never reused, which is the loss of caching that redaction was meant to
avoid, with a dead row left behind as well.

**The cache key is derived from the request URL**, including its query string, and the entry that is
written holds the request object itself. So a credential would reach storage twice over: once in the
key (a hash, not recoverable) and once in the serialized request (recoverable, and the actual leak).
Refusing to cache the request removes both, and the key exactly: no key is computed for a request a
filter has already turned away.

## Goals / Non-Goals

**Goals:**

- No credential is written to the cache database at all — not in the entry, not in the key — and the
  request that leaves the process still carries it.
- A response the origin forbade storing does not get replayed from storage.
- One ingest performs one history write and one collection-existence check, not one per activation.
- Every one of the three lands with a test that fails against the current code.

**Non-Goals:**

- No cache for a request that carries a credential. Keeping one means reaching into hishel's cache
  transport; decision 1 records why every alternative was rejected.
- No encryption of the cache database. The cache is disposable and holds public news; the credential
  is the one thing in it worth protecting, and not writing it is simpler and stronger than encrypting
  it.
- No switch to `SpecificationPolicy`. Vendor responses do not carry usable freshness metadata, so the
  TTL is the mechanism that makes the cache worth having; the change narrows that policy with the
  safety directives instead of replacing it.
- No change to what any command or tool returns, and no spec delta — see the proposal's Capabilities
  section.
- No migration of existing cache rows. Deleting a disposable cache is the operator's call.

## Decisions

### 1. A request whose query string carries a credential is not cached at all

`build_news_client` gains a request filter beside the response one. `FilterPolicy` runs request
filters first, and a filter that returns `False` hands the request straight to the origin: no key is
computed, no entry is looked up, nothing is written. Mediastack's `access_key` therefore never reaches
the database — nor the row, nor the key, nor the response stored beside them.

The rule is a predicate on the URL rather than on a source, so it covers the query parameter the other
four APIs document as their alternative authentication form: a source that switches to one does not
silently start writing its key to disk because nobody revisited a list of names.

Why not redaction, which is what this plan first chose: redacting the stored request does keep the
value out of the database, but hishel reuses an entry only when the stored request URL equals the live
one byte for byte (see Context). A redacted URL never does, so the entry would be written and then
never served — the cache is lost either way, and redaction additionally leaves a row of dead weight
and depends on a storage wrapper staying in step with hishel's storage interface. Refusing to cache
says the same thing in one filter, on the extension point hishel documents, and leaves the request
that goes upstream untouched.

Alternatives considered:

- **Redact the credential in a storage wrapper.** Rejected on the URL-equality evidence above: it
  loses the cache anyway, and pays for that with a wrapper that must mirror `AsyncBaseStorage`.
- **Redact the credential and relax the reuse check.** Rejected: the check lives in hishel's private
  cache transport — `IdleClient` is constructed inside `AsyncCache.handle_request` — so relaxing it
  means subclassing internals this project does not otherwise touch.
- **Take the credential out of the URL and inject it below the cache.** Rejected as the right answer
  to a different question: it would keep the cache and take the key out of the cache key too, but it
  moves key handling out of the adapters and into the HTTP layer, against the boundary
  `docs/NEWS_SOURCES.md` documents, and it deserves its own change and ADR.
- **Move the Mediastack key into a header.** Rejected as no fix at all: headers are persisted in the
  same entry, so the secret moves rather than disappears.
- **Encrypt the database.** Rejected: it needs a key management story for a disposable cache holding
  public news, and it protects the news along with the secret.

### 2. `_CacheOnlySuccesses` also refuses what the origin forbade storing

The response filter keeps its "only 2xx" rule and gains a second: a response whose `Cache-Control`
carries `no-store` or `no-cache` is not stored. Parsing is by directive name, case-insensitive, with
any `=value` or quoted form ignored — the two directives take no argument, so nothing more is needed.

`private` is treated as not storable too. This client's cache is a shared on-disk file, so a response
marked for a single user is not one to keep, even though the current upstreams are public feeds. It
costs nothing today and stops a future credentialed source from being cached because nobody revisited
this filter.

The name `_CacheOnlySuccesses` stops describing what it does; it becomes `_CacheWhatMayBeStored`, and
its docstring records why the TTL policy is deliberately narrower than the specification rather than
wider.

Both decisions are recorded durably in [ADR 0014](../../../docs/adr/0014-cache-only-what-may-be-kept.md),
which also narrows [ADR 0009](../../../docs/adr/0009-hishel-caching.md) — the caching ADR whose point 5
assumed the key would simply sit inside a hashed cache key, and whose non-goals ruled out parsing
`Cache-Control` at all.

Alternatives considered:

- **Honour freshness metadata as well** (`max-age`, `must-revalidate`, `Expires`). Rejected on
  evidence: vendor responses do not carry usable freshness headers, which is why the TTL extension
  exists. Honouring directives selectively — the safety ones — is the part that matters.
- **Switch to `SpecificationPolicy`.** Rejected: it would stop respecting the TTL, which is the
  cache's whole value here.
- **Drop the response filter** and rely on `SpecificationPolicy`. Rejected: loses both the 2xx rule
  and the TTL.

### 3. Batch the history write and ensure the collection once

`vector/history.py` gains a batched write: ensure the collection once, then one `upsert(wait=True)`
with every point. `record_activation` stays in the public surface — tests and callers use it to seed
one point — and becomes a single-element delegation to the batch. The ingest write phase loses its
per-activation loop and makes one call.

This narrows the failure window that `fix-ingest-and-forecast-integrity` closes by ordering: fewer
round trips inside the write phase means fewer places to be interrupted, and the two changes are
independent — either alone is correct, both together are better.

Ordering note for the callers: the batched write must be the one that runs before the `news` upsert
once that change lands, exactly as the per-activation loop did.

## Risks / Trade-offs

- **Existing cache rows keep the credential.** → The rule is not retroactive, and the change does not
  delete a user's cache. `docs/NEWS_SOURCES.md` documents that the cache is disposable and that
  removing `.cache/hishel/news.db` clears it. A startup check in the cache path logs a warning when
  the database still holds a request with a credential parameter, so the situation announces itself
  rather than sitting silent.
- **A credentialed request is fetched every time, so Mediastack loses its cache.** → Accepted, and
  recorded here rather than discovered later: the cache only ever spared a repeat of the same query
  inside the fifteen-minute TTL, and keeping it costs a dependency on hishel internals (decision 1).
  Mediastack's free tier is the tightest of the five, so the cost is real but bounded, and the
  aggregator already degrades one source rather than failing the whole fetch.
- **A blanket request rule could refuse more than it should.** → It keys off a parameter name in the
  query string, so an ordinary request is untouched: the other four sources authenticate with a
  header and GDELT needs no key, so their entries are cached exactly as before.
- **Honouring `no-store`/`no-cache` costs requests against free-tier quotas.** → Accepted knowingly;
  see the proposal's Impact. The TTL still covers every response that does not forbid storing.
- **`private` treated as not storable is stricter than the RFC requires of a private cache.** → This
  cache is a file on disk, not a per-user private cache, so the reading is the conservative one. If a
  source ever needs `private` responses cached, that is a deliberate change with its own reasoning.
- **One batched upsert is all-or-nothing at the Qdrant call**, whereas the per-row loop could leave a
  partial result. → That is the improvement, not the risk: partial history was the state the ordering
  fix exists to make recoverable, and one call removes the intermediate state entirely.

## Migration Plan

No data migration and no configuration change. The request rule, the directive handling and the
batching take effect on the next run. Rolling back is reverting the change: the old code caches a
credentialed request again, and it reads a cache written by the new code without complaint, because
the new code only writes fewer entries of exactly the same shape.

The one operator action is optional and privacy-motivated: removing `.cache/hishel/news.db` clears
rows written before the fix. It is safe at any time and costs one cache miss per source.
