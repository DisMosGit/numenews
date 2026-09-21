"""The news layer's public entry point.

Callers that want one call and a merged list use :func:`fetch_news`; callers that want to control
the client or inject sources (phases 5 to 7, and every test) use
:class:`~numenews.news.aggregator.NewsAggregator` directly.
"""

from __future__ import annotations

from numenews.config import Settings, get_settings
from numenews.models import DateRange, NewsItem, Topic
from numenews.news.aggregator import NewsAggregator
from numenews.news.http import build_news_client


async def fetch_news(
    topic: Topic,
    date_range: DateRange,
    *,
    settings: Settings | None = None,
) -> list[NewsItem]:
    """Fetch every configured source and return the merged result.

    The client is created here and closed on the way out: the sqlite cache it owns cannot be reused
    after being closed, so a caller that wants a long-lived client should build one with
    :func:`~numenews.news.http.build_news_client` and drive
    :class:`~numenews.news.aggregator.NewsAggregator` itself.

    Args:
        topic: What to search for.
        date_range: The inclusive UTC range to keep.
        settings: Configuration, including the news keys. Defaults to
            :func:`numenews.config.get_settings`.

    Raises:
        NewsSourceError: when no source is configured at all.
    """
    resolved = settings if settings is not None else get_settings()
    async with build_news_client(resolved) as client:
        return await NewsAggregator.from_settings(resolved, client).fetch_all(topic, date_range)
