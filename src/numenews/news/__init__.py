"""News-source adapters: GDELT, NewsAPI, GNews, Mediastack and Currents.

Every adapter implements the same :class:`~numenews.news.protocol.NewsSource` Protocol and shares
one ``httpx`` client with a fifteen-minute ``hishel`` cache
(:func:`~numenews.news.http.build_news_client`). The aggregator queries them in parallel and keeps
the answers that arrived, so a single broken feed degrades the result instead of failing the run.

Only GDELT works without a key, which is why the default demo path needs no configuration
(``AGENTS.md``); the other four are constructed from :class:`~numenews.config.Settings` only when
their key is present. :func:`~numenews.news.api.fetch_news` is the whole layer in one call.
"""

from __future__ import annotations

from numenews.news.aggregator import NewsAggregator, build_sources
from numenews.news.api import fetch_news
from numenews.news.currents import CurrentsSource
from numenews.news.errors import (
    NewsSourceAuthError,
    NewsSourceError,
    NewsSourceHTTPError,
    NewsSourceParseError,
    NewsSourceRateLimitError,
    NewsSourceTransportError,
)
from numenews.news.gdelt import GDELTSource
from numenews.news.gnews import GNewsSource
from numenews.news.http import NEWS_CACHE_TTL_SECONDS, build_news_client
from numenews.news.mediastack import MediastackSource
from numenews.news.newsapi import NewsAPISource
from numenews.news.protocol import NewsSource

__all__ = [
    "NEWS_CACHE_TTL_SECONDS",
    "CurrentsSource",
    "GDELTSource",
    "GNewsSource",
    "MediastackSource",
    "NewsAPISource",
    "NewsAggregator",
    "NewsSource",
    "NewsSourceAuthError",
    "NewsSourceError",
    "NewsSourceHTTPError",
    "NewsSourceParseError",
    "NewsSourceRateLimitError",
    "NewsSourceTransportError",
    "build_news_client",
    "build_sources",
    "fetch_news",
]
