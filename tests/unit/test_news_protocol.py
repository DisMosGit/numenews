"""The ``NewsSource`` Protocol and the failure vocabulary around it.

The roadmap's Definition of Done for this task is that ``mypy --strict`` checks the structural
typing, so the fake below is deliberately a plain class — no base class, no inheritance — and the
module-level :func:`accepts` takes a :class:`~numenews.news.NewsSource`. If the Protocol and the
fake drift apart, the type check fails, not just these assertions.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from numenews.models import DateRange, NewsId, NewsItem, Topic
from numenews.news import (
    NewsSource,
    NewsSourceAuthError,
    NewsSourceError,
    NewsSourceHTTPError,
    NewsSourceParseError,
    NewsSourceRateLimitError,
    NewsSourceTransportError,
)


class FakeSource:
    """A minimal source: a class attribute for ``name`` and one coroutine for ``fetch``."""

    name = "fake"

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Echo one item whose title repeats the topic, whatever the range."""
        return [
            NewsItem(
                id=NewsId(uuid4()),
                title=topic.query,
                text=f"published between {date_range.start} and {date_range.end}",
                source=self.name,
                date=date_range.start,
                url="https://example.test/fake",
            )
        ]


def accepts(source: NewsSource) -> str:
    """Return a source's name; the argument type is the structural check `mypy --strict` runs."""
    return source.name


def test_a_plain_class_satisfies_the_protocol() -> None:
    """No inheritance is needed: the shape is the contract."""
    assert accepts(FakeSource()) == "fake"


async def test_the_fake_fetches_with_the_protocol_signature() -> None:
    """`fetch` takes the two query models and returns `list[NewsItem]`."""
    items = await FakeSource().fetch(
        Topic(query="politics"),
        DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21)),
    )

    assert [item.title for item in items] == ["politics"]
    assert items[0].source == "fake"


def test_http_errors_carry_their_status_and_retry_decision() -> None:
    """A 5xx is worth another attempt, a 4xx is not; the status travels with the message."""
    transient = NewsSourceHTTPError(
        "mediastack returned HTTP 503: service unavailable", status_code=503
    )
    permanent = NewsSourceHTTPError("mediastack returned HTTP 400: invalid date", status_code=400)

    assert transient.status_code == 503
    assert transient.retryable is True
    assert permanent.status_code == 400
    assert permanent.retryable is False


def test_authentication_errors_are_never_retried() -> None:
    """A rejected key stays rejected: retrying would only spend quota."""
    error = NewsSourceAuthError("newsapi returned HTTP 401: apiKeyMissing", status_code=401)

    assert isinstance(error, NewsSourceHTTPError)
    assert error.retryable is False


def test_rate_limit_errors_always_retry_and_carry_retry_after() -> None:
    """A 429 is retryable; `Retry-After` travels from the response to the retry policy."""
    with_header = NewsSourceRateLimitError(
        "currents returned HTTP 429", status_code=429, retry_after=2.5
    )
    without_header = NewsSourceRateLimitError("gdelt returned HTTP 429", status_code=429)

    assert with_header.retryable is True
    assert with_header.retry_after == 2.5
    assert without_header.retry_after is None


def test_transport_and_parse_errors_are_news_source_errors() -> None:
    """The aggregator can catch one base class and still keep our own bugs propagating."""
    assert isinstance(NewsSourceTransportError("connection reset"), NewsSourceError)
    assert NewsSourceTransportError("connection reset").retryable is True
    assert isinstance(NewsSourceParseError("not json"), NewsSourceError)
    assert NewsSourceParseError("not json").retryable is False


def test_the_base_error_is_not_retryable() -> None:
    """The default is "do not retry": a subclass opts in explicitly."""
    assert NewsSourceError("plain failure").retryable is False


@pytest.mark.parametrize("error_class", [NewsSourceAuthError, NewsSourceParseError])
def test_errors_subclass_the_news_source_error(error_class: type[NewsSourceError]) -> None:
    """Every failure the layer raises is catchable as `NewsSourceError`."""
    assert issubclass(error_class, NewsSourceError)
