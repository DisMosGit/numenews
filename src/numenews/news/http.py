"""One HTTP client for all five sources: cached, retried, mapped onto our errors.

The client is an ``httpx.AsyncClient`` whose transport is wrapped by ``hishel``'s RFC 9111 cache.
The cache runs in hishel's *filter* mode rather than its specification mode, which is a deliberate
choice: none of the five news APIs sends a freshness header that RFC 9111 could use, so the
specification policy would treat every stored response as stale and never answer from the cache. The
policy that makes the roadmap's fifteen-minute TTL real is the storage's ``default_ttl`` — a hishel
extension, not a caching rule — and the filter mode is what lets it apply.

Failures become :mod:`numenews.news.errors` exceptions here, once, so no adapter and no aggregator
looks at a status code: the aggregator catches :class:`~numenews.news.errors.NewsSourceError` and
keeps the sources that answered, while the retry policy asks the exception whether another attempt
is worth making.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from hishel import AsyncSqliteStorage, BaseFilter, FilterPolicy, Response
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

# How long a cached response may answer a request. The roadmap fixes fifteen minutes: the five APIs
# count requests against a daily quota, and a forecast run is measured in minutes, not seconds.
NEWS_CACHE_TTL_SECONDS = 900.0

# One attempt's budget. The five feeds answer quickly, and a hung connection should not hold the
# aggregator's `gather` open.
_REQUEST_TIMEOUT_SECONDS = 10.0

# A retry either waits for `Retry-After` or backs off on its own; both are capped, so a source that
# asks for an hour does not stall the run.
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

    The caller owns the client and closes it (``async with`` or ``aclose``). Closing the client
    closes its sqlite storage for good, so there is deliberately no module-level singleton to reuse
    by accident; phase 6 may keep one alive inside its application context.

    Args:
        settings: Configuration holding the cache directory. Defaults to
            :func:`numenews.config.get_settings`.
    """
    resolved = settings if settings is not None else get_settings()
    storage = AsyncSqliteStorage(
        database_path=resolved.cache_dir / _CACHE_DB_NAME,
        default_ttl=NEWS_CACHE_TTL_SECONDS,
    )
    return AsyncCacheClient(
        storage=storage,
        policy=FilterPolicy(response_filters=[_CacheOnlySuccesses()]),
        timeout=httpx.Timeout(_REQUEST_TIMEOUT_SECONDS),
        headers={"user-agent": _USER_AGENT},
    )


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
) -> httpx.Response:
    """Fetch ``url`` with retries and return the successful response.

    Only the URL without its query string is logged: Mediastack takes its key as a query parameter,
    so the full URL would put a credential in the logs.

    Args:
        client: The shared client from :func:`build_news_client`.
        source: Source name, used in log records and error messages.
        url: Endpoint, without query parameters.
        params: Query parameters, passed to ``httpx`` as a mapping.
        headers: Per-source headers, such as an API key or an authorization scheme.

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
                client, source=source, url=url, params=params, headers=headers
            )
    raise AssertionError("unreachable: tenacity re-raises the last failure")


async def _request_once(
    client: httpx.AsyncClient,
    *,
    source: str,
    url: str,
    params: Mapping[str, str | int],
    headers: Mapping[str, str] | None,
) -> httpx.Response:
    """Send one request and translate its failure modes into our exception hierarchy."""
    try:
        response = await client.get(url, params=params, headers=headers)
    except httpx.TransportError as error:
        raise NewsSourceTransportError(f"{source} is unreachable: {error}") from error
    _raise_for_status(response, source=source)
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


def _raise_for_status(response: httpx.Response, *, source: str) -> None:
    """Raise the failure that matches the status code, and return for a 2xx."""
    status = response.status_code
    if 200 <= status < 300:
        return
    message = f"{source} returned HTTP {status}: {_body_snippet(response)}"
    if status in (401, 403):
        raise NewsSourceAuthError(message, status_code=status)
    if status == 429:
        raise NewsSourceRateLimitError(
            message, status_code=status, retry_after=_retry_after_seconds(response)
        )
    raise NewsSourceHTTPError(message, status_code=status)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Return the ``Retry-After`` header in seconds when it holds a number."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        # An HTTP-date is legal in `Retry-After`; the exponential backoff is a fine stand-in.
        return None


def _body_snippet(response: httpx.Response) -> str:
    """Return the start of an error body on one line, for the exception message."""
    collapsed = " ".join(response.text.split())
    return collapsed[:_ERROR_BODY_CHARS] or "<empty body>"
