"""What a caller asks the news layer for: a topic and a date range.

Both types cross the boundary between the interfaces (CLI, MCP tools) and the news adapters, so
they are frozen and strict like every other domain model: an adapter receives a validated range,
never two loose ``date`` arguments.
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
