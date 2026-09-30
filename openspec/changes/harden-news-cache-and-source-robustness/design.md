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
the request straight upstream without looking in or writing to the cache. That makes "do not cache
credentialed requests" expressible, but only as a filter outcome — it is not a redaction hook.

**The cache key is derived from the request URL**, including its query string, and the entry that is
written holds the request object itself. So the credential reaches storage twice over: once in the key
(a hash, not recoverable) and once in the serialized request (recoverable, and the actual leak).

## Goals / Non-Goals

**Goals:**

- No credential is recoverable from the cache database, and the request that leaves the process still
  carries it.
- A response the origin forbade storing does not get replayed from storage.
- One ingest performs one history write and one collection-existence check, not one per activation.
- Every one of the three lands with a test that fails against the current code.

**Non-Goals:**

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

### 1. Redact the credential in a storage wrapper, not in a filter

A storage wrapper sits between the client and `AsyncSqliteStorage`. `create_entry` — the only write
path `FilterPolicy` reaches, since revalidation belongs to the specification path — replaces the URL
of the request it is about to persist with the same URL whose credential parameter's value is a fixed
placeholder. Every other method delegates unchanged.

Why a storage wrapper rather than a request filter: a filter can only exclude a request from the
cache, so protecting the credential that way costs Mediastack its entire cache — the source that most
needs it, since the audit's own docstring notes the free tier. Redacting at the storage boundary keeps
the cache working, keeps the request that goes upstream untouched, and puts the redaction at the one
place where "what is written" is decided.

The cache key still reflects the real URL, so the key is a hash of a string holding the credential
rather than the credential itself. That is acceptable — a hash is not recoverable — and it avoids
blending one key's quota accounting with another's. The placeholder is a fixed string, so a stored
entry always has one canonical form per cache key.

Alternatives considered:

- **Exclude credentialed requests from caching** (a request filter returning `False`). Rejected: safe
  but expensive, and it silently changes how hard the project leans on Mediastack's quota.
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

The name `_CacheOnlySuccesses` stops describing what it does; it becomes something like
`_CacheWhatMayBeStored`, and its docstring records why the TTL policy is deliberately narrower than
the specification rather than wider.

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

- **Existing cache rows keep the credential.** → The redaction is not retroactive, and the change does
  not delete a user's cache. `docs/NEWS_SOURCES.md` documents that the cache is disposable and that
  removing `.cache/hishel/news.db` clears it. A startup check in the cache path logs a warning when
  the database still holds a request with a credential parameter, so the situation announces itself
  rather than sitting silent.
- **A credential-redacting wrapper depends on hishel internals.** → It only calls the declared
  `AsyncBaseStorage` methods and copies the request with `dataclasses.replace`, and `Request` and
  `Response` are dataclasses by construction. If a hishel upgrade changes the storage interface, the
  failure is an import or signature error at startup, caught by the existing cache tests rather than
  by a quiet leak.
- **Honouring `no-store`/`no-cache` costs requests against free-tier quotas.** → Accepted knowingly;
  see the proposal's Impact. The TTL still covers every response that does not forbid storing.
- **`private` treated as not storable is stricter than the RFC requires of a private cache.** → This
  cache is a file on disk, not a per-user private cache, so the reading is the conservative one. If a
  source ever needs `private` responses cached, that is a deliberate change with its own reasoning.
- **One batched upsert is all-or-nothing at the Qdrant call**, whereas the per-row loop could leave a
  partial result. → That is the improvement, not the risk: partial history was the state the ordering
  fix exists to make recoverable, and one call removes the intermediate state entirely.

## Migration Plan

No data migration and no configuration change. The redaction, the directive handling and the batching
take effect on the next run. Rolling back is reverting the change: the storage wrapper and the filter
write a superset of what they used to, and a cache written by the fixed code is read by the old code
without complaint — entries simply hold a placeholder where a credential used to be, and are never
replayed upstream because the requests that produced them are not re-sent from storage.

The one operator action is optional and privacy-motivated: removing `.cache/hishel/news.db` clears
rows written before the fix. It is safe at any time and costs one cache miss per source.
