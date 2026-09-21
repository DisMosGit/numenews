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
    """

    model_config = ConfigDict(frozen=True, strict=True)

    number: int
    date: date
    news_id: NewsId
    context: str
