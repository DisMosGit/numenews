"""Failures a news source can report.

Every adapter raises a subclass of :class:`NewsSourceError`, which lets the aggregator degrade
gracefully with a single ``except``: one broken feed never takes the whole fetch down, while a bug
in our own code (any other exception) still propagates instead of hiding behind an empty result.

``retryable`` lives on the exception rather than at the call site, because whether another attempt
is worth making is a property of the failure: a 503 or a dropped connection is, a 401 never is.
"""

from __future__ import annotations


class NewsSourceError(Exception):
    """Base class for every failure inside the news layer."""

    retryable: bool = False


class NewsSourceHTTPError(NewsSourceError):
    """A source answered with an unexpected HTTP status.

    The body snippet is part of the message: the five APIs disagree on error envelopes (one of them
    answers a rate limit with plain text), so the raw text is more useful than any modelled shape.
    """

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code
        # 5xx is the server asking for another attempt; 4xx is not.
        self.retryable = status_code >= 500


class NewsSourceAuthError(NewsSourceHTTPError):
    """401 or 403: the key is missing, invalid, or lacks access to the requested function."""


class NewsSourceRateLimitError(NewsSourceHTTPError):
    """429: the source's burst or daily quota is exhausted.

    ``retry_after`` is the ``Retry-After`` header in seconds when the source sent one; the retry
    policy honours it and otherwise backs off on its own.
    """

    def __init__(self, message: str, *, status_code: int, retry_after: float | None = None) -> None:
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after
        self.retryable = True


class NewsSourceTransportError(NewsSourceError):
    """The request never produced a response (DNS, connection or read timeout)."""

    retryable = True


class NewsSourceParseError(NewsSourceError):
    """The body was not the JSON the source documents, or not JSON at all."""
