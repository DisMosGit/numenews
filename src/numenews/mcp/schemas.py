"""The wire schemas of the MCP tools: what a client may send, in the form it sends it.

The domain models of :mod:`numenews.models` are ``strict`` by decision (phase 1): a Python ``str``
is never coerced into a ``date``, a ``list`` never into a ``tuple``. That is right inside the
process and wrong on the wire — an MCP client speaks JSON, where dates are strings, tuples are
arrays and ids are UUID strings, and every one of those must be parsed rather than rejected.

This module is the boundary where that looseness is accepted, exactly as
:mod:`numenews.agents.schemas` is the boundary for what a language model may answer. The rule is the
same in both directions: the outside world validates into a DTO here, the DTO converts with
:meth:`to_domain` into the frozen domain model the layers below expect, and the layers never see a
loose field.

Every constraint that the domain model enforces is enforced here too — a reversed range, a reversed
date filter and a ``strength`` outside ``[0, 1]`` are refused at the wire, so ``to_domain`` itself
cannot fail and a bad argument reads as a tool error the model can correct.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from numenews.models import (
    DateRange,
    NewsFilter,
    NewsId,
    NewsItem,
    Pattern,
    PatternId,
    PatternType,
)

#: The collections ``query_qdrant`` may search. Phase 3 only built semantic read paths for the two
#: 768d collections whose entities are searchable by meaning: ``news`` (``search_news``) and
#: ``patterns`` (``find_similar_patterns``). ``number_history`` is read exactly by ``get_history``,
#: and ``numbers``/``forecasts``/``digests`` have no read path yet, so offering them here would be a
#: promise the storage layer cannot keep.
type CollectionName = Literal["news", "patterns"]


class DateRangeInput(BaseModel):
    """The inclusive date range of ``fetch_news``, as the client sends it.

    ``start == end`` is a valid one-day range. The reversed-range rule lives in
    :class:`~numenews.models.query.DateRange` and is mirrored here so the error names the argument
    the model passed, rather than surfacing from a conversion inside the tool.
    """

    model_config = ConfigDict(frozen=True)

    start: date = Field(description="First publication day to keep, inclusive (YYYY-MM-DD).")
    end: date = Field(description="Last publication day to keep, inclusive (YYYY-MM-DD).")

    @model_validator(mode="after")
    def _reject_reversed_range(self) -> Self:
        """Refuse a range whose start lies after its end, as :class:`DateRange` does."""
        if self.start > self.end:
            raise ValueError("date_range.start must not be after date_range.end")
        return self

    def to_domain(self) -> DateRange:
        """Return the validated :class:`~numenews.models.query.DateRange`."""
        return DateRange(start=self.start, end=self.end)


class NewsFilterInput(BaseModel):
    """The optional narrowing arguments of ``query_qdrant``, as the client sends them.

    Every field is optional and ``None`` means "do not constrain", like
    :class:`~numenews.models.query.NewsFilter`, whose rules this mirrors.
    """

    model_config = ConfigDict(frozen=True)

    date_from: date | None = Field(default=None, description="Earliest publication day, inclusive.")
    date_to: date | None = Field(default=None, description="Latest publication day, inclusive.")
    source: str | None = Field(default=None, description="Publisher name, exactly as stored.")
    numerology_value: int | None = Field(
        default=None, description="The item's reduced value (1-9, or 11/22/33)."
    )
    master_number: bool | None = Field(
        default=None, description="Whether the item's value is a master number (11, 22 or 33)."
    )

    @model_validator(mode="after")
    def _reject_reversed_dates(self) -> Self:
        """Refuse a window whose start lies after its end, as :class:`NewsFilter` does."""
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("filters.date_from must not be after filters.date_to")
        return self

    def to_domain(self) -> NewsFilter:
        """Return the validated :class:`~numenews.models.query.NewsFilter`."""
        return NewsFilter(
            date_from=self.date_from,
            date_to=self.date_to,
            source=self.source,
            numerology_value=self.numerology_value,
            master_number=self.master_number,
        )


class PatternInput(BaseModel):
    """A pattern ``save_pattern`` is asked to store, in the client's JSON shape.

    The domain :class:`~numenews.models.patterns.Pattern` is strict, so the ids arrive as strings,
    the numbers as an array and the ``discovered_at`` timestamp as an RFC 3339 string; the
    conversion wraps ids back into ``NewsId``/``PatternId`` and the arrays into tuples.

    ``discovered_at`` is optional for the same reason it is on the model: a pattern the model just
    described has no moment yet, and ``save_pattern`` stamps the current UTC time.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(description="Stable pattern id (UUID); re-saving the same id replaces it.")
    type: PatternType = Field(description="resonance | repetition | master | symbol | hidden")
    numbers: list[int] = Field(description="The numbers the connection is about.")
    news_ids: list[UUID] = Field(description="Ids of the news items the pattern connects.")
    strength: Annotated[float, Field(ge=0.0, le=1.0, description="Confidence between 0 and 1.")]
    interpretation: str = Field(description="One sentence saying what the connection is.")
    discovered_at: datetime | None = Field(
        default=None, description="When it was found, if known; the server stamps it otherwise."
    )

    def to_domain(self) -> Pattern:
        """Return the validated :class:`~numenews.models.patterns.Pattern`."""
        return Pattern(
            id=PatternId(self.id),
            type=self.type,
            numbers=tuple(self.numbers),
            news_ids=tuple(NewsId(news_id) for news_id in self.news_ids),
            strength=self.strength,
            interpretation=self.interpretation,
            discovered_at=self.discovered_at,
        )


class CollectionQueryResult(BaseModel):
    """What ``query_qdrant`` found: the collection it searched and the entities it returned.

    The roadmap's sketch returned ``list[dict]``; ``AGENTS.md`` rules dicts out of every
    boundary, so
    the two searchable entities of phase 3 — :class:`~numenews.models.news.NewsItem` and
    :class:`~numenews.models.patterns.Pattern` — are returned as a typed union. ``query`` is echoed
    back so a client can match a result to the question it asked.
    """

    model_config = ConfigDict(frozen=True)

    collection: CollectionName = Field(description="Which collection was searched.")
    query: str = Field(description="The text the search embedded.")
    items: tuple[NewsItem | Pattern, ...] = Field(
        default=(), description="The matching entities, best match first."
    )


__all__ = [
    "CollectionName",
    "CollectionQueryResult",
    "DateRangeInput",
    "NewsFilterInput",
    "PatternInput",
]
