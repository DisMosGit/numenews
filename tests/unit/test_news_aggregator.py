"""The aggregator's merging policy, tested with fakes.

What is under test here is what happens *between* the sources — parallel execution, degradation, the
range filter and the de-duplication key. HTTP belongs to the integration suite.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from numenews.config import Settings
from numenews.models import DateRange, NewsId, NewsItem, Topic
from numenews.news import NewsAggregator, NewsSourceError, build_sources

TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))


def _item(
    title: str,
    *,
    source: str = "example.com",
    published: date = date(2026, 9, 21),
) -> NewsItem:
    """Return a news item with just enough variety to be identified."""
    return NewsItem(
        id=NewsId(uuid4()),
        title=title,
        text=f"{title} body",
        source=source,
        date=published,
        url=f"https://example.test/{title.replace(' ', '-').lower()}",
    )


class _FakeSource:
    """A source that returns prepared items or raises a prepared failure."""

    def __init__(self, name: str, result: list[NewsItem] | BaseException) -> None:
        self.name = name
        self._result = result

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return the prepared result, or raise it when it is an exception."""
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


async def test_two_failing_sources_still_leave_three_sources_of_items() -> None:
    """Roadmap 2.8: a broken feed degrades the result instead of failing the run."""
    aggregator = NewsAggregator(
        [
            _FakeSource("a", [_item("from a")]),
            _FakeSource("b", NewsSourceError("b returned HTTP 503")),
            _FakeSource("c", [_item("from c")]),
            _FakeSource("d", NewsSourceError("d returned HTTP 429")),
            _FakeSource("e", [_item("from e")]),
        ]
    )

    items = await aggregator.fetch_all(TOPIC, RANGE)

    assert [item.title for item in items] == ["from a", "from c", "from e"]


async def test_every_source_failing_returns_an_empty_list() -> None:
    """An empty result is better than an exception when every feed is down; the warnings say why."""
    aggregator = NewsAggregator(
        [_FakeSource("a", NewsSourceError("down")), _FakeSource("b", NewsSourceError("down"))]
    )

    assert await aggregator.fetch_all(TOPIC, RANGE) == []


async def test_items_are_de_duplicated_on_title_source_and_date() -> None:
    """The same article from two feeds stays one item; another publisher's copy is a second."""
    twin = _item("Summit ends", source="example.com")
    aggregator = NewsAggregator(
        [
            _FakeSource("a", [twin, _item("Summit ends", source="other.example")]),
            _FakeSource(
                "b", [twin, _item("Summit ends", source="example.com", published=date(2026, 9, 20))]
            ),
        ]
    )

    items = await aggregator.fetch_all(TOPIC, RANGE)

    assert [item.source for item in items] == ["example.com", "other.example", "example.com"]
    assert [item.date for item in items] == [
        date(2026, 9, 21),
        date(2026, 9, 21),
        date(2026, 9, 20),
    ]


async def test_items_outside_the_range_are_dropped() -> None:
    """The aggregator holds every source to the same boundary, whatever its own filter did."""
    aggregator = NewsAggregator(
        [
            _FakeSource(
                "a",
                [
                    _item("too early", published=date(2026, 9, 14)),
                    _item("inside", published=date(2026, 9, 15)),
                    _item("last day", published=date(2026, 9, 21)),
                    _item("too late", published=date(2026, 9, 22)),
                ],
            )
        ]
    )

    items = await aggregator.fetch_all(TOPIC, RANGE)

    assert [item.title for item in items] == ["inside", "last day"]


async def test_without_a_single_source_the_configuration_error_is_raised() -> None:
    """Nothing to query is a configuration problem, not an empty news day."""
    with pytest.raises(NewsSourceError, match="no news sources are configured"):
        await NewsAggregator([]).fetch_all(TOPIC, RANGE)


async def test_a_bug_of_ours_is_not_degraded_away() -> None:
    """Only source failures degrade; a `RuntimeError` from an adapter is a defect and surfaces."""
    aggregator = NewsAggregator(
        [_FakeSource("a", [_item("fine")]), _FakeSource("b", RuntimeError("a bug"))]
    )

    with pytest.raises(RuntimeError, match="a bug"):
        await aggregator.fetch_all(TOPIC, RANGE)


async def test_the_aggregator_reports_its_sources_in_request_order() -> None:
    """Phases 6 and 7 introspect the source list; it is the order the requests are made in."""
    aggregator = NewsAggregator([_FakeSource("a", []), _FakeSource("b", [])])

    assert [source.name for source in aggregator.sources] == ["a", "b"]


async def test_build_sources_includes_only_the_configured_feeds(settings: Settings) -> None:
    """GDELT is always there; the other four appear exactly when their key does."""
    client = httpx.AsyncClient()
    try:
        assert [source.name for source in build_sources(settings, client)] == ["gdelt"]

        configured = settings.model_copy(
            update={
                "newsapi_key": SecretStr("newsapi-key"),
                "gnews_key": SecretStr("gnews-key"),
                "mediastack_key": SecretStr("mediastack-key"),
                "currents_key": SecretStr("currents-key"),
            }
        )

        assert [source.name for source in build_sources(configured, client)] == [
            "gdelt",
            "newsapi",
            "gnews",
            "mediastack",
            "currents",
        ]
    finally:
        await client.aclose()
