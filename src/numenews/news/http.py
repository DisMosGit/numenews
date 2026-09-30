"""One HTTP client for all five sources: cached, retried, mapped onto our errors.

The client is an ``httpx.AsyncClient`` whose transport is wrapped by ``hishel``'s RFC 9111 cache.
The cache runs in hishel's *filter* mode rather than its specification mode, which is a deliberate
choice: none of the five news APIs sends a freshness header that RFC 9111 could use, so the
specification policy would treat every stored response as stale and never answer from the cache. The
policy that makes the fifteen-minute TTL real is the storage's ``default_ttl`` — a hishel
extension, not a caching rule — and the filter mode is what lets it apply.

The cache never holds a credential. Mediastack is the one source that authenticates through the
query string, and hishel persists both the request it stored a response for and a key derived from
its URL, so a request carrying a credential is not cached at all — see
:class:`_CacheOnlyCredentialFreeRequests`. The request that leaves the process keeps its key and the
source still authenticates; it is the entry that is never written. Redacting the stored URL instead
was the first plan, and the reason it does not work is worth knowing: hishel reuses an entry only
when the stored request URL equals the live one, so a redacted entry could never be served.

Failures become :mod:`numenews.news.errors` exceptions here, once, so no adapter and no aggregator
looks at a status code: the aggregator catches :class:`~numenews.news.errors.NewsSourceError` and
keeps the sources that answered, while the retry policy asks the exception whether another attempt
is worth making.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path

import httpx
from hishel import AsyncSqliteStorage, BaseFilter, FilterPolicy, Request, Response
from hishel.httpx import AsyncCacheClient
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from numenews.config import Settings, get_settings
from numenews.logging import get_logger
from numenews.news.errors import (
    NewsSourceAuthError,
    NewsSourceError,
    NewsSourceHTTPError,
    NewsSourceParseError,
    NewsSourceRateLimitError,
    NewsSourceTransportError,
)

logger = get_logger(__name__)

# How long a cached response may answer a request. The cache TTL is fifteen minutes: the five APIs
# count requests against a daily quota, and a forecast run is measured in minutes, not seconds.
NEWS_CACHE_TTL_SECONDS = 900.0

# One attempt's budget. The five feeds answer quickly, and a hung connection should not hold the
# aggregator's `gather` open.
_REQUEST_TIMEOUT_SECONDS = 10.0

# A retry either waits for `Retry-After` or backs off on its own; both are capped, so a source that
# asks for an hour does not stall the run. The cap is applied twice on purpose —
# `_retry_after_seconds` clamps the header into it as the hint enters the system, and `_wait` clamps
# whatever the exception carries — so no path, including a `retry_after` set by hand, reaches
# tenacity's sleep unbounded.
_MAX_RETRY_WAIT_SECONDS = 15.0

_RETRY_ATTEMPTS = 3

# The cache database lives inside `Settings.cache_dir`. hishel creates the directory and drops a
# `.gitignore` holding `*` into it, so the file never shows up in `git status`.
_CACHE_DB_NAME = "news.db"

# Identify the project rather than the underlying httpx: an unidentified bulk client is what the
# throttles are aimed at.
_USER_AGENT = "numenews/0.1 (+https://github.com/DisMosGit/numenews)"

# An error body is included in the message, truncated: one of the five answers a rate limit with
# plain text and another with HTML, so the raw text is worth more than any modelled envelope.
_ERROR_BODY_CHARS = 200

# The query parameters that carry a credential, matched case-insensitively. Mediastack is the only
# source that authenticates through the query string today, but the other four document a query
# parameter as the alternative form, so the set is deliberately wider than today's traffic: a source
# that switches to a parameter must not start writing its key to disk because nobody revisited it.
_CREDENTIAL_PARAMS = ("access_key", "access_token", "api_key", "apikey", "token")

# What a credential looks like in a query string, as one pattern used twice: on a URL, to refuse a
# request the cache must not store, and on the bytes of a stored entry, to find one an older version
# wrote. The lookbehind is what keeps a parameter that merely *ends* in a credential name —
# `access_key_backup` — from counting: a query parameter starts at `?` or `&`, nothing else does.
_CREDENTIAL_PARAM_PATTERN = (
    rf"(?<=[?&])(?:{'|'.join(re.escape(name) for name in _CREDENTIAL_PARAMS)})="
)
_CREDENTIAL_IN_URL = re.compile(_CREDENTIAL_PARAM_PATTERN, re.IGNORECASE)
_CREDENTIAL_IN_STORED_ENTRY = re.compile(_CREDENTIAL_PARAM_PATTERN.encode(), re.IGNORECASE)


def _carries_credential(url: str) -> bool:
    """Return whether ``url`` authenticates with a query parameter.

    The URL is where a credential can hide from everything else in this module: the logs carry the
    endpoint without its query string, and a header is not part of the URL at all, but hishel both
    derives its cache key from the full URL and writes the request itself into the entry. A caller
    asks this question to keep such a request out of the cache entirely.

    Args:
        url: The request URL.

    Returns:
        ``True`` when a query parameter carries a credential.
    """
    return _CREDENTIAL_IN_URL.search(url) is not None


class _CacheOnlyCredentialFreeRequests(BaseFilter[Request]):
    """Keep a request that authenticates through its query string out of the cache entirely.

    A request filter runs before hishel computes the cache key, and returning ``False`` here hands
    the request straight to the origin: no key is derived from it, no entry is looked up and nothing
    is written. That is stronger than redacting the credential out of the stored request, and it is
    the only one of the two that works — hishel reuses an entry only when the stored request URL
    equals the live one, so a redacted entry would be written once and then never served.

    The rule is about the URL rather than a source, so it covers the credential query parameter the
    other four APIs document as their alternative form. What it costs is the cache for such a
    source: its repeats within the TTL reach the origin again. The request itself is untouched, so
    authentication is unaffected.
    """

    def needs_body(self) -> bool:
        """Decide from the URL alone, without reading the body."""
        return False

    def apply(self, item: Request, body: bytes | None) -> bool:
        """Return whether this request may be cached."""
        return not _carries_credential(item.url)


class _CacheOnlySuccesses(BaseFilter[Response]):
    """Keep error responses out of the cache.

    hishel stores whatever the transport returned, so without this filter a cached 503 would be
    replayed for the whole TTL instead of being retried, and a 429 would hide the quota reset.
    """

    def needs_body(self) -> bool:
        """Decide from the status line alone, without reading the body."""
        return False

    def apply(self, item: Response, body: bytes | None) -> bool:
        """Return whether this response may be stored."""
        return 200 <= item.status_code < 300


def build_news_client(settings: Settings | None = None) -> AsyncCacheClient:
    """Return the cached client the adapters share for one run.

    The policy carries a filter for each direction: a request whose query string authenticates is
    not cached at all (see :class:`_CacheOnlyCredentialFreeRequests`), and a response the origin
    forbade storing is not written either. A database written before the request rule existed still
    holds the real key, and this function is where that announces itself rather than sitting
    silent — see :func:`_warn_if_credentials_are_cached`.

    The caller owns the client and closes it (``async with`` or ``aclose``). Closing the client
    closes its sqlite storage for good, so there is deliberately no module-level singleton to reuse
    by accident; the MCP server may keep one alive inside its application context.

    Args:
        settings: Configuration holding the cache directory. Defaults to
            :func:`numenews.config.get_settings`.
    """
    resolved = settings if settings is not None else get_settings()
    database_path = resolved.cache_dir / _CACHE_DB_NAME
    _warn_if_credentials_are_cached(database_path)
    storage = AsyncSqliteStorage(
        database_path=database_path,
        default_ttl=NEWS_CACHE_TTL_SECONDS,
    )
    return AsyncCacheClient(
        storage=storage,
        policy=FilterPolicy(
            request_filters=[_CacheOnlyCredentialFreeRequests()],
            response_filters=[_CacheOnlySuccesses()],
        ),
        timeout=httpx.Timeout(_REQUEST_TIMEOUT_SECONDS),
        headers={"user-agent": _USER_AGENT},
    )


def _warn_if_credentials_are_cached(database_path: Path) -> None:
    """Log a warning when the cache already holds a credential, from before this rule.

    The refusal to cache a credentialed request is not retroactive, and this package does not delete
    a cache it did not create: an entry written by an older version still holds the real key, and
    removing it is the operator's call. What this check adds is that the situation announces itself,
    so "is my cache carrying a key?" has an answer in the logs instead of only in the file.

    The read is deliberately defensive. It runs before the client opens the database, it is bounded
    to the one column holding a request, and every failure — no ``entries`` table yet, a database
    locked by another process, a file that is not a database — becomes a debug record rather than an
    exception, because a diagnostic must never be the reason a run cannot start.

    Args:
        database_path: The cache database, which may not exist yet.
    """
    if not database_path.exists():
        return
    try:
        # Opening read-write rather than `mode=ro`: a WAL database cannot be opened read-only
        # unless its `-shm` file already exists and is writable, and a cache left in that state is
        # exactly the one worth warning about. The timeout keeps another process's lock from
        # stalling startup.
        connection = sqlite3.connect(database_path, timeout=1.0)
    except sqlite3.Error as error:
        logger.debug("news.http.cache_check_failed", error=str(error))
        return
    try:
        for parameter in _CREDENTIAL_PARAMS:
            # `instr` searches the serialized entry inside sqlite, so a cache holding no credential
            # never has its rows — response bodies included — read into this process at all.
            rows = connection.execute(
                "SELECT data FROM entries WHERE instr(data, ?) > 0",
                (f"{parameter}=".encode(),),
            ).fetchall()
            # Confirmed in Python because the SQL above matches the bytes of the name anywhere in
            # the entry: a body that merely mentions `access_key=` must not be reported.
            if any(
                _CREDENTIAL_IN_STORED_ENTRY.search(row[0])
                for row in rows
                if isinstance(row[0], bytes)
            ):
                logger.warning(
                    "news.http.cache_holds_credential",
                    database=str(database_path),
                    parameter=parameter,
                )
                return
    except sqlite3.Error as error:
        logger.debug("news.http.cache_check_failed", error=str(error))
    finally:
        connection.close()


def parse_json[ModelT: BaseModel](
    response: httpx.Response, model: type[ModelT], *, source: str
) -> ModelT | None:
    """Validate a response body into ``model``; ``None`` means the body was empty.

    GDELT answers a query with no matches with an empty body instead of an empty list, so "empty"
    is a result rather than a failure. Anything else that is not valid JSON for ``model`` is a
    :class:`~numenews.news.errors.NewsSourceParseError`.

    Args:
        response: A response whose body has already been read.
        model: The private response model of the adapter that called this.
        source: Source name, used in the error message.
    """
    if not response.content:
        return None
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise NewsSourceParseError(
            f"{source} sent a body that is not the documented JSON: {error}"
        ) from error


async def get_response(
    client: httpx.AsyncClient,
    *,
    source: str,
    url: str,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None = None,
    rate_limit_statuses: tuple[int, ...] = (),
) -> httpx.Response:
    """Fetch ``url`` with retries and return the successful response.

    Only the URL without its query string is logged: Mediastack takes its key as a query parameter,
    so the full URL would put a credential in the logs.

    The failure is classified inside the attempt, before the retry policy decides anything:
    ``_request_once`` translates a non-2xx response into our exception hierarchy, and tenacity then
    asks that exception whether another attempt is worth making. A status named in
    ``rate_limit_statuses`` is therefore a rate limit for the whole of that decision, not a
    translation applied once the attempts are already spent.

    Args:
        client: The shared client from :func:`build_news_client`.
        source: Source name, used in log records and error messages.
        url: Endpoint, without query parameters.
        params: Query parameters, passed to ``httpx`` as a mapping.
        headers: Per-source headers, such as an API key or an authorization scheme.
        rate_limit_statuses: Statuses this source spends on an exhausted quota although HTTP
            reserves them for something else — GNews answers a spent daily quota with 403. They are
            read as :class:`~numenews.news.errors.NewsSourceRateLimitError` during the request, so
            the central policy retries them and honours their ``Retry-After``.

    Raises:
        NewsSourceError: on a transport failure, a timeout, or a non-2xx status.
    """
    logger.debug("news.http.request", source=source, url=url)
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=_wait,
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    ):
        with attempt:
            return await _request_once(
                client,
                source=source,
                url=url,
                params=params,
                headers=headers,
                rate_limit_statuses=rate_limit_statuses,
            )
    raise AssertionError("unreachable: tenacity re-raises the last failure")


async def _request_once(
    client: httpx.AsyncClient,
    *,
    source: str,
    url: str,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None,
    rate_limit_statuses: tuple[int, ...],
) -> httpx.Response:
    """Send one request and translate its failure modes into our exception hierarchy."""
    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.TransportError as error:
        raise NewsSourceTransportError(f"{source} is unreachable: {error}") from error
    _raise_for_status(response, source=source, rate_limit_statuses=rate_limit_statuses)
    return response


def _is_retryable(error: BaseException) -> bool:
    """Ask the failure itself whether another attempt is worth making."""
    return isinstance(error, NewsSourceError) and error.retryable


def _wait(retry_state: RetryCallState) -> float:
    """Wait for ``Retry-After`` when the source sent one, otherwise back off exponentially."""
    outcome = retry_state.outcome
    error = outcome.exception() if outcome is not None else None
    if isinstance(error, NewsSourceRateLimitError) and error.retry_after is not None:
        return min(error.retry_after, _MAX_RETRY_WAIT_SECONDS)
    return wait_exponential_jitter(initial=1.0, max=_MAX_RETRY_WAIT_SECONDS)(retry_state)


def _raise_for_status(
    response: httpx.Response, *, source: str, rate_limit_statuses: tuple[int, ...] = ()
) -> None:
    """Raise the failure that matches the status code, and return for a 2xx.

    Classification happens here, inside the attempt, because the retry policy reads the exception's
    class and its ``retryable`` flag: a status this source spends on its quota must already be a
    rate limit when the attempt ends, or tenacity decides on the wrong failure.
    ``rate_limit_statuses`` is consulted before the generic 401/403 branch for exactly that reason —
    a status named there reaches :func:`_wait` with whatever ``Retry-After`` the answer carried. A
    2xx is a success even when named in the tuple: turning one into a failure would report a
    caller's mistake as a source failure.

    Args:
        response: The response whose status decides the failure.
        source: Source name, used in the error message.
        rate_limit_statuses: Extra statuses to read as an exhausted quota beyond 429.
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    message = f"{source} returned HTTP {status}: {_body_snippet(response)}"
    if status in rate_limit_statuses or status == 429:
        raise NewsSourceRateLimitError(
            message, status_code=status, retry_after=_retry_after_seconds(response)
        )
    if status in (401, 403):
        raise NewsSourceAuthError(message, status_code=status)
    raise NewsSourceHTTPError(message, status_code=status)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Return the ``Retry-After`` hint in whole seconds, clamped, or ``None`` when unusable.

    RFC 9110 gives the header two forms, and only one of them is a wait this client can use:
    ``delta-seconds`` is one or more ASCII digits with optional surrounding whitespace, and that is
    the whole accepted grammar. The other form, an HTTP-date, becomes a delay only by comparing it
    with the response's own ``Date``, which is more clock arithmetic than a retry hint is worth, so
    it falls to the exponential backoff like every other value the grammar rejects. Rejecting them
    here rather than guarding at sleep time is deliberate: ``nan``, ``inf``, ``-5``, ``3.5`` and
    ``1e9`` all satisfy ``float()`` but none is delta-seconds, and a ``nan`` reaching :func:`_wait`
    is a ``ValueError`` escaping the ``NewsSourceError`` hierarchy, which the aggregator re-raises
    and fails the whole fetch over. ``None`` stays the single answer for "no usable hint" — not a
    new sentinel — so :func:`_wait` reads it as "back off on your own".

    The accepted value is clamped to ``_MAX_RETRY_WAIT_SECONDS`` as it enters the system, so "a
    retry hint is finite, non-negative and bounded" holds for everything that reads the exception
    later; the clamp in :func:`_wait` is then a second line of defence rather than the only one.

    Args:
        response: The response whose ``Retry-After`` header is read.

    Returns:
        The hint in whole seconds, clamped to ``[0, _MAX_RETRY_WAIT_SECONDS]``, or ``None`` when the
        header is absent or outside the delta-seconds grammar.
    """
    value = response.headers.get("retry-after")
    if value is None:
        return None
    seconds = value.strip()
    # `str.isdigit` is true for non-ASCII digits such as "٣" (U+0663), which delta-seconds does not
    # allow, so the ASCII check is part of the grammar rather than a nicety.
    if not (seconds.isascii() and seconds.isdigit()):
        return None
    return min(float(seconds), _MAX_RETRY_WAIT_SECONDS)


def _body_snippet(response: httpx.Response) -> str:
    """Return the start of an error body on one line, for the exception message."""
    collapsed = " ".join(response.text.split())
    return collapsed[:_ERROR_BODY_CHARS] or "<empty body>"
