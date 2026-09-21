"""The GDELT adapter: no key, an ``artlist`` envelope, and plain-text failures.

The fixture is a hand-written response in the documented shape rather than a recording: GDELT
throttles this environment to a 429, and a fixture pins the field names the parser depends on.
"""

from __future__ import annotations

from datetime import date
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient

from numenews.models import DateRange, NewsId, Topic
from numenews.news import NewsSourceParseError, NewsSourceRateLimitError
from numenews.news.gdelt import GDELTSource

from .conftest import news_fixture

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))


@pytest.mark.integration
async def test_fetch_maps_the_artlist_envelope(news_client: AsyncCacheClient) -> None:
    """Two of the four fixture articles are usable; the malformed ones are skipped, not fatal."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(
            return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
        )

        items = await GDELTSource(news_client).fetch(TOPIC, RANGE)

    assert [item.title for item in items] == [
        "11th hour deal reached on the budget",
        "Summit ends without an agreement",
    ]

    first = items[0]
    assert first.text == first.title  # artlist has no description field
    assert first.source == "example.com"
    assert first.date == date(2026, 9, 21)
    assert first.url == "https://www.example.com/politics/11th-hour-deal"
    assert first.id == NewsId(uuid5(NAMESPACE_URL, first.url))

    assert items[1].date == date(2026, 9, 20)
    assert items[1].source == "news.example.org"


@pytest.mark.integration
async def test_fetch_sends_the_documented_query(news_client: AsyncCacheClient) -> None:
    """The request is the DOC 2.0 artlist query, with GDELT's own UTC timestamp format."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(ENDPOINT).mock(
            return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
        )

        await GDELTSource(news_client).fetch(TOPIC, RANGE)

        params = route.calls[-1].request.url.params

    assert params["query"] == "politics"
    assert params["mode"] == "artlist"
    assert params["format"] == "json"
    assert params["sort"] == "datedesc"
    assert params["maxrecords"] == "75"
    assert params["startdatetime"] == "20260915000000"
    assert params["enddatetime"] == "20260921235959"


@pytest.mark.integration
async def test_fetch_returns_nothing_for_an_empty_body(news_client: AsyncCacheClient) -> None:
    """A query with no matches returns an empty body, which is a result rather than an error."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, content=b""))

        assert await GDELTSource(news_client).fetch(TOPIC, RANGE) == []


@pytest.mark.integration
async def test_fetch_reports_a_plain_text_body_as_a_parse_error(
    news_client: AsyncCacheClient,
) -> None:
    """GDELT answers a bad request with HTTP 200 and HTML; that must not parse into nonsense."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(return_value=httpx.Response(200, text="Invalid mode."))

        with pytest.raises(NewsSourceParseError):
            await GDELTSource(news_client).fetch(TOPIC, RANGE)


@pytest.mark.integration
async def test_fetch_reports_a_throttle_with_the_plain_text_message(
    news_client: AsyncCacheClient,
    instant_retries: None,
) -> None:
    """The throttle is a 429 with a plain-text body and no `Retry-After`."""
    with respx.mock(assert_all_called=False) as router:
        router.get(ENDPOINT).mock(
            return_value=httpx.Response(429, text="Please limit requests to one every 5 seconds")
        )

        with pytest.raises(NewsSourceRateLimitError) as caught:
            await GDELTSource(news_client).fetch(TOPIC, RANGE)

    assert "Please limit requests" in str(caught.value)
    assert caught.value.retry_after is None
