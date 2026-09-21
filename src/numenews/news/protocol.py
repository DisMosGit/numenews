"""The one interface every news adapter implements.

``NewsSource`` is a Protocol rather than an abstract base class: the five adapters share a shape,
not an implementation worth inheriting, and structural typing lets a test stub satisfy it without
importing the layer. ``mypy --strict`` proves the real adapters match the shape, and
``tests/unit/test_news_protocol.py`` proves a fake does too.
"""

from __future__ import annotations

from typing import Protocol

from numenews.models import DateRange, NewsItem, Topic


class NewsSource(Protocol):
    """A news feed that can answer a topic within a date range."""

    @property
    def name(self) -> str:
        """Short, stable identifier used in logs and as the ``NewsItem.source`` fallback."""
        ...

    async def fetch(self, topic: Topic, date_range: DateRange) -> list[NewsItem]:
        """Return the items this source has for ``topic`` within ``date_range``.

        Items are returned as the API ordered them; filtering to the range and de-duplication are
        the aggregator's job, so every source is held to the same rules.

        Raises:
            NewsSourceError: on any failure, including a missing or rejected key.
        """
        ...
