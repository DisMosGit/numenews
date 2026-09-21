"""What a caller asks the storage layer for: a topic, a date range and a news filter.

Every type here crosses the boundary between the interfaces (CLI, MCP tools) and the layers below,
so they are frozen and strict like every other domain model: an adapter receives a validated range,
never two loose ``date`` arguments, and the vector layer receives a validated filter, never a
hand-built Qdrant ``Filter``.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class Topic(BaseModel):
    """What to search the five news feeds for.

    ``query`` is passed through to each API in that API's own syntax (quoted phrases, boolean
    operators); the model only rejects a query that is empty once trimmed, because a blank query
    would ask for the firehose rather than for news about something.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    query: str

    @field_validator("query")
    @classmethod
    def _reject_blank_query(cls, value: str) -> str:
        """Return the query without surrounding whitespace, or refuse an empty one."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("topic query must not be blank")
        return trimmed


class DateRange(BaseModel):
    """Inclusive range of publication dates, as UTC calendar days.

    ``start == end`` is a valid one-day range. The range is authoritative in the aggregator: each
    API filters with whatever precision it offers, and the aggregator drops anything left outside
    the range, so every source is held to the same boundary.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    start: date
    end: date

    @model_validator(mode="after")
    def _reject_reversed_range(self) -> Self:
        """Refuse a range whose start lies after its end."""
        if self.start > self.end:
            raise ValueError("date range start must not be after its end")
        return self


class NewsFilter(BaseModel):
    """The subset of indexed news fields a caller may narrow a search by.

    Every field is optional and ``None`` means "do not constrain": an all-default
    :class:`NewsFilter` matches every item. The model is the typed front end of the Qdrant payload
    filters, so a caller never builds a storage ``Filter`` by hand and the layer above never imports
    ``qdrant_client``; ``date_from``/``date_to`` are inclusive UTC calendar days, matching
    :class:`DateRange`.

    ``numerology_value`` compares a single value: the phase-3 collections store the reduced value of
    the whole item, so a filter is "the item's number is 7", not "7 occurs somewhere in it".
    """

    model_config = ConfigDict(frozen=True, strict=True)

    date_from: date | None = None
    date_to: date | None = None
    source: str | None = None
    numerology_value: int | None = None
    master_number: bool | None = None

    @model_validator(mode="after")
    def _reject_reversed_dates(self) -> Self:
        """Refuse a window whose start lies after its end, as :class:`DateRange` does."""
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("news filter date_from must not be after date_to")
        return self
