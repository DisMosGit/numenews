"""Long-term memory: which number was activated when and where."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from numenews.models.ids import NewsId


class NumberActivation(BaseModel):
    """One occurrence of a number in one news item.

    One row of the payload-only ``number_history`` collection (phase 3.7); ``context`` is the
    snippet the number was read in, which is the excerpt the forecast prompt shows the agent
    (phase 8.3).

    ``numerology_value`` is the item's own reduced value, copied onto the row (phase 8.1) so that a
    history read answers "what was the day read under" without a second lookup in ``news``. ``None``
    is the same documented "not computed" as on :class:`~numenews.models.news.NewsItem`: the payload
    writes no key at all for it (``exclude_none``), and it must not be confused with ``0``, which no
    reduced value ever takes.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    number: int
    date: date
    news_id: NewsId
    context: str
    numerology_value: int | None = None
