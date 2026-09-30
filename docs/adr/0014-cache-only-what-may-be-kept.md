# 14. Cache only what may be kept

## Status

Accepted

## Date

2026-09-30

## Context

[ADR 0009](0009-hishel-caching.md) chose `hishel`'s filter mode for the news cache and recorded two
rules: only 2xx responses are stored, and key material must stay on the right side of the cache key —
four adapters send their key in a header, while Mediastack documents `access_key` in the query string
only. It also recorded, as an explicit non-goal, that no `Cache-Control` parsing would happen.

Two of those positions turned out to be wrong in practice, and this ADR records the correction.

**A credential in the query string reached the database.** `hishel` writes the request it stored a
response for, and derives its cache key from that request's URL, so Mediastack's key was persisted in
cleartext in `.cache/hishel/news.db` — in the serialized request, not merely inside a hash. The module
already took care not to log the query string, so this was a case of the same care not being applied
to what was stored. The obvious fix, redacting the value before the entry is written, does not work:
`hishel` serves a stored entry only when the stored request URL equals the live one byte for byte
(`IdleClient.next` in `hishel/_core/_spec.py`, and the same comparison in the filter path). A redacted
URL never equals a live one, so such an entry would be written and then never reused — the cache would
be lost anyway, and a row of dead weight left behind. Relaxing that comparison means replacing
`hishel`'s private cache transport, which is a dependency this project does not want for a disposable
cache of public news.

**A response the origin forbade storing was stored anyway.** `FilterPolicy` applies only the filters it
is handed, so the specification's directive handling never runs: a response carrying `no-store`,
`no-cache` or `private` was kept and replayed for the whole TTL without revalidation. That is a
deliberate deviation from RFC 9111 — the five APIs send no usable freshness metadata, which is why the
storage's `default_ttl` exists — but it was broader than the vendors require. Ignoring freshness
metadata and ignoring a refusal to store are different things: the first is what makes the cache worth
having here, the second overrides the origin's own instruction about its content.

## Decision

We will narrow what the news cache is allowed to keep, in `build_news_client`
(`src/numenews/news/http.py`), using the request and response filters `hishel`'s filter mode is built
around. The storage, the TTL, the database location and the one-client-per-run rule of ADR 0009 are
unchanged.

1. **A request that authenticates through its query string is not cached at all.** A request filter
   refuses it before `hishel` computes a cache key, so no key is derived from the credential, no entry
   is looked up and nothing is written. The rule is a predicate on the URL — the credential parameter
   names the five APIs document — rather than on a source, so a source that switches to a query
   parameter does not start writing its key to disk by omission. The request that leaves the process is
   untouched: refusing it the cache must not refuse it its key. This applies to every adapter.
2. **A response whose `Cache-Control` carries `no-store`, `no-cache` or `private` is not stored**, in
   addition to the 2xx rule. Parsing is by directive name, case-insensitively, with any `=value`
   ignored: the three take no argument that changes whether the response may be kept. `no-cache`
   belongs here because this cache has no specification path to revalidate through, so keeping such a
   response would mean serving it unchecked; `private` because the database is a shared file on disk,
   not a per-user cache.
3. **Honouring those directives is the deliberate limit.** `max-age`, `Expires` and the rest are still
   ignored, and the storage TTL remains the freshness rule. Only a refusal to store is binding.
4. **A cache written before this decision is not deleted, but it is not silent either.** Building the
   client logs a `news.http.cache_holds_credential` warning when the database still holds a request
   with a credential parameter. Removing `.cache/hishel/news.db` is the documented, optional operator
   action.

## Consequences

- **What becomes easier.** The cache database can be copied, backed up or left on a shared machine
  without carrying an API key, and the reason is a property of the code rather than of an operator's
  cleanup. A source that answers with a refusal to store is now believed, so a change of mind by a
  vendor cannot be silently overridden by a fifteen-minute TTL.
- **What becomes harder.** An operator who ran an older version has one manual step to take, and the
  project cannot take it for them without deleting a file it did not create.
- **What it costs.** Mediastack loses its cache: a repeat of the same query inside the TTL reaches the
  origin again, so its free-tier quota (100 calls a month) is spent faster than before. This is the
  price of not reaching into `hishel`'s internals, and it is bounded — the TTL only ever spared
  repeats inside fifteen minutes, the aggregator makes one request per source per run, and a source
  failure degrades that source rather than failing the fetch. Response volume can also rise for any
  vendor that sends one of the three directives, which is the intended effect.
- **What we explicitly did not do.** No redaction of a stored request, no relaxation of `hishel`'s
  reuse comparison, no credential injection below the cache, no encryption of the database, and no
  switch to the specification policy. Injecting the credential at the transport boundary is the one
  rejected alternative that would have kept the cache *and* removed the key from the cache key; it was
  rejected because it moves key handling out of the adapters and into the HTTP layer, against the
  boundary `docs/NEWS_SOURCES.md` documents, and deserves its own change.
- **Follow-up work.** If keeping Mediastack's cache ever matters more than the internal dependency,
  transport-boundary injection is the design to revisit. If a source starts sending usable freshness
  headers, the specification policy becomes viable again and ADRs 0009 and this one are superseded
  rather than edited.

## References

- [ADR 0009](0009-hishel-caching.md) — the caching decision this one narrows
- [`docs/NEWS_SOURCES.md`](../NEWS_SOURCES.md) §The cache — the operator-facing description
- [`src/numenews/news/http.py`](../../src/numenews/news/http.py) — `_CacheOnlyCredentialFreeRequests`,
  `_CacheWhatMayBeStored`, `_forbids_storing` and `_warn_if_credentials_are_cached`
- [RFC 9111 §5.2](https://www.rfc-editor.org/rfc/rfc9111#section-5.2) — `Cache-Control` directives
