"""The whole news layer against five mocked endpoints.

This is the phase-2 acceptance test: five sources, two of them broken, and one call that still
returns the news the other three had — plus the rules that must hold whatever each API did (the
range filter, the de-duplication key, and a configuration with no keys at all).
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx
from hishel.httpx import AsyncCacheClient
from pydantic import SecretStr

from numenews.config import Settings
from numenews.models import DateRange, Topic
from numenews.news import NewsAggregator, fetch_news

from .conftest import news_fixture

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWSAPI = "https://newsapi.org/v2/everything"
GNEWS = "https://gnews.io/api/v4/search"
MEDIASTACK = "https://api.mediastack.com/v1/news"
CURRENTS = "https://api.currentsapi.services/v1/search"

TOPIC = Topic(query="politics")
RANGE = DateRange(start=date(2026, 9, 15), end=date(2026, 9, 21))
KEYS: dict[str, SecretStr] = {
    "newsapi_key": SecretStr("newsapi-key"),
    "gnews_key": SecretStr("gnews-key"),
    "mediastack_key": SecretStr("mediastack-key"),
    "currents_key": SecretStr("currents-key"),
}
ALL_SOURCE_NAMES = ["gdelt", "newsapi", "gnews", "mediastack", "currents"]

GDELT_TITLES = [
    "11th hour deal reached on the budget",
    "Summit ends without an agreement",
]
NEWSAPI_TITLES = [
    "The 11th hour deal",
    "Resonance in the markets",
    "A headline with neither description nor content",
]
GNEWS_TITLES = ["Twenty-two nations sign the accord", "A lonely headline"]
MEDIASTACK_TITLES = ["The eleventh hour budget", "A headline with no description"]
CURRENTS_TITLES = ["The thirty-third rescue", "A headline with no description"]


def _mock_all_succeeding(router: respx.MockRouter) -> None:
    """Answer every endpoint with its recorded fixture."""
    router.get(GDELT).mock(
        return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
    )
    router.get(NEWSAPI).mock(
        return_value=httpx.Response(200, content=news_fixture("newsapi_everything.json"))
    )
    router.get(GNEWS).mock(
        return_value=httpx.Response(200, content=news_fixture("gnews_search.json"))
    )
    router.get(MEDIASTACK).mock(
        return_value=httpx.Response(200, content=news_fixture("mediastack_news.json"))
    )
    router.get(CURRENTS).mock(
        return_value=httpx.Response(200, content=news_fixture("currents_search.json"))
    )


@pytest.mark.integration
async def test_five_sources_with_two_failures_still_produce_news(
    news_client: AsyncCacheClient,
    settings: Settings,
    instant_retries: None,
) -> None:
    """The phase's Definition of Done: two of five sources down, three still answer."""
    configured = settings.model_copy(update=KEYS)

    with respx.mock(assert_all_called=False) as router:
        router.get(GDELT).mock(
            return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
        )
        router.get(NEWSAPI).mock(
            return_value=httpx.Response(200, content=news_fixture("newsapi_everything.json"))
        )
        router.get(GNEWS).mock(return_value=httpx.Response(500, text="internal error"))
        router.get(MEDIASTACK).mock(return_value=httpx.Response(503, text="service unavailable"))
        router.get(CURRENTS).mock(
            return_value=httpx.Response(200, content=news_fixture("currents_search.json"))
        )

        aggregator = NewsAggregator.from_settings(configured, news_client)

        assert [source.name for source in aggregator.sources] == ALL_SOURCE_NAMES

        items = await aggregator.fetch_all(TOPIC, RANGE)

    assert [item.title for item in items] == [*GDELT_TITLES, *NEWSAPI_TITLES, *CURRENTS_TITLES]


@pytest.mark.integration
async def test_a_narrow_range_is_applied_to_every_source(
    news_client: AsyncCacheClient,
    settings: Settings,
) -> None:
    """Each API filters with its own precision; the aggregator is what makes the range exact."""
    configured = settings.model_copy(update=KEYS)
    one_day = DateRange(start=date(2026, 9, 21), end=date(2026, 9, 21))

    with respx.mock(assert_all_called=False) as router:
        _mock_all_succeeding(router)

        items = await NewsAggregator.from_settings(configured, news_client).fetch_all(
            TOPIC, one_day
        )

    assert [item.title for item in items] == [
        GDELT_TITLES[0],
        NEWSAPI_TITLES[0],
        GNEWS_TITLES[0],
        MEDIASTACK_TITLES[0],
        CURRENTS_TITLES[0],
    ]
    assert {item.date for item in items} == {date(2026, 9, 21)}


@pytest.mark.integration
async def test_the_same_article_from_two_feeds_is_one_item(
    news_client: AsyncCacheClient,
    settings: Settings,
) -> None:
    """Syndication with different tracking URLs still shares title, publisher and date."""
    configured = settings.model_copy(
        update={"newsapi_key": KEYS["newsapi_key"]}  # GDELT is always there
    )
    gdelt_body = (
        b'{"articles": [{"url": "https://www.example.com/a?utm=gdelt", "title": "Summit ends",'
        b' "seendate": "20260920T100000Z", "domain": "example.com"}]}'
    )
    newsapi_body = (
        b'{"status": "ok", "articles": [{"source": {"name": "example.com"},'
        b' "title": "Summit ends", "description": "Same story.",'
        b' "url": "https://www.example.com/a?utm=newsapi",'
        b' "publishedAt": "2026-09-20T10:00:00Z"}]}'
    )

    with respx.mock(assert_all_called=False) as router:
        router.get(GDELT).mock(return_value=httpx.Response(200, content=gdelt_body))
        router.get(NEWSAPI).mock(return_value=httpx.Response(200, content=newsapi_body))

        items = await NewsAggregator.from_settings(configured, news_client).fetch_all(TOPIC, RANGE)

    assert len(items) == 1
    assert items[0].url == "https://www.example.com/a?utm=gdelt"  # the first feed wins


@pytest.mark.integration
async def test_without_keys_only_gdelt_is_queried(
    news_client: AsyncCacheClient,
    settings: Settings,
) -> None:
    """The default demo path: no configuration, one source, a real result."""
    with respx.mock(assert_all_called=False) as router:
        route = router.get(GDELT).mock(
            return_value=httpx.Response(200, content=news_fixture("gdelt_artlist.json"))
        )

        aggregator = NewsAggregator.from_settings(settings, news_client)

        assert [source.name for source in aggregator.sources] == ["gdelt"]

        items = await aggregator.fetch_all(TOPIC, RANGE)

        assert route.call_count == 1

    assert [item.title for item in items] == GDELT_TITLES


@pytest.mark.integration
async def test_fetch_news_runs_the_whole_layer(settings: Settings) -> None:
    """`fetch_news` builds a cached client, queries every configured feed and closes the client."""
    configured = settings.model_copy(update=KEYS)

    with respx.mock(assert_all_called=False) as router:
        _mock_all_succeeding(router)

        items = await fetch_news(TOPIC, RANGE, settings=configured)

    assert [item.title for item in items] == [
        *GDELT_TITLES,
        *NEWSAPI_TITLES,
        *GNEWS_TITLES,
        *MEDIASTACK_TITLES,
        *CURRENTS_TITLES,
    ]


@pytest.mark.integration
async def test_fetch_news_survives_every_source_failing(
    settings: Settings,
    instant_retries: None,
) -> None:
    """Five broken feeds produce an empty list and five warnings, not an exception."""
    configured = settings.model_copy(update=KEYS)

    with respx.mock(assert_all_called=False) as router:
        for endpoint in (GDELT, NEWSAPI, GNEWS, MEDIASTACK, CURRENTS):
            router.get(endpoint).mock(return_value=httpx.Response(500, text="down"))

        assert await fetch_news(TOPIC, RANGE, settings=configured) == []
