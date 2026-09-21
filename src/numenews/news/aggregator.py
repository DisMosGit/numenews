"""Ask every configured source at once, then keep what came back.

Five free plans mean five ways to fail today, and a reading built from three feeds is worth more
than no reading because a fourth was down. So the sources run concurrently, a source failure becomes
a warning, and the surviving items are held to the two rules that must not depend on any one API:
the requested date range, and one copy of each ``(title, source, date)``.

"Degrade" applies to source failures only. A bug in our own code — a ``KeyError`` from a malformed
mapping, a cancelled task — is re-raised rather than swallowed: hiding a defect behind a quietly
thinner result is worse than a loud failure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import date

import httpx

from numenews.config import Settings
from numenews.logging import get_logger
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.currents import CurrentsSource
from numenews.news.errors import NewsSourceError
from numenews.news.gdelt import GDELTSource
from numenews.news.gnews import GNewsSource
from numenews.news.mediastack import MediastackSource
from numenews.news.newsapi import NewsAPISource
from numenews.news.protocol import NewsSource

logger = get_logger(__name__)

# What makes two items the same article. The roadmap names the key, and nothing beyond the
# adapters' own trimming is normalised, so titles that differ by one character stay two items.
type DeduplicationKey = tuple[str, str, date]


def build_sources(settings: Settings, client: httpx.AsyncClient) -> list[NewsSource]:
    """Return every source the settings configure, in request order.

    GDELT needs no key and is always present; the other four are built by their own
    ``from_settings``, which returns ``None`` when its key is missing, so a half-configured machine
    quietly queries fewer feeds instead of failing.
    """
    candidates: list[NewsSource | None] = [
        GDELTSource(client),
        NewsAPISource.from_settings(settings, client),
        GNewsSource.from_settings(settings, client),
        MediastackSource.from_settings(settings, client),
        CurrentsSource.from_settings(settings, client),
    ]
    return [source for source in candidates if source is not None]


class NewsAggregator:
    """Query a set of sources concurrently and merge their items."""

    def __init__(self, sources: Sequence[NewsSource]) -> None:
        self._sources = tuple(sources)

    @classmethod
    def from_settings(cls, settings: Settings, client: httpx.AsyncClient) -> NewsAggregator:
        """Return an aggregator over the sources ``settings`` configure."""
        return cls(build_sources(settings, client))

    @property
    def sources(self) -> tuple[NewsSource, ...]:
        """The sources this aggregator queries, in request order."""
        return self._sources

    async def fetch_all(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return the merged, range-filtered, de-duplicated items of every source.

        Items keep their order: source by source, and within a source the order the API returned
        them, so a caller can rely on the result being stable between identical runs.

        Args:
            topic: What to search for.
            date_range: The inclusive UTC range every item is checked against.

        Raises:
            NewsSourceError: when no source is configured at all — a configuration error rather
                than a network failure, and the one failure worth surfacing to a caller.
        """
        if not self._sources:
            raise NewsSourceError(
                "no news sources are configured: set NEWSAPI_KEY, GNEWS_KEY, MEDIASTACK_KEY "
                "or CURRENTS_KEY to query more than GDELT"
            )
        results = await asyncio.gather(
            *(source.fetch(topic, date_range) for source in self._sources),
            return_exceptions=True,
        )

        items: list[NewsItem] = []
        seen: set[DeduplicationKey] = set()
        duplicates = 0
        for source, result in zip(self._sources, results, strict=True):
            if isinstance(result, BaseException):
                if not isinstance(result, NewsSourceError):
                    raise result
                logger.warning("news.source.failed", source=source.name, error=str(result))
                continue
            logger.debug("news.source.fetched", source=source.name, items=len(result))
            for item in result:
                if not date_range.start <= item.date <= date_range.end:
                    continue
                key: DeduplicationKey = (item.title, item.source, item.date)
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                items.append(item)

        logger.info(
            "news.fetch.complete",
            sources=len(self._sources),
            items=len(items),
            duplicates=duplicates,
        )
        return items
