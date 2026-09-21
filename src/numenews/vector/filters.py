"""Translate the typed filters of :mod:`numenews.models.query` into Qdrant filters.

Qdrant types stay in this module: the layers above filter with :class:`~numenews.models.NewsFilter`
and never import ``qdrant_client``. The translation is pure, so the shape of the generated filter is
unit-tested without a server.

Date bounds are half-open on the server side — ``>= day 00:00:00Z`` and ``< next day 00:00:00Z`` —
because a news ``date`` is a UTC calendar day: an inclusive ``date_to`` must not silently exclude
the items published during its own day. The bounds are ``datetime`` objects, which is what Qdrant's
own model stores; the client serializes them to RFC 3339 on the wire, the same shape the payloads
are written in.
"""

from __future__ import annotations

from datetime import timedelta

from qdrant_client.models import Condition, DatetimeRange, FieldCondition, Filter, MatchValue

from numenews.models import NewsFilter
from numenews.vector.payloads import day_start


def build_news_filter(filters: NewsFilter | None) -> Filter:
    """Return the Qdrant filter for ``filters``; ``None`` or an empty model matches everything."""
    if filters is None:
        return Filter()
    conditions: list[Condition] = []
    if filters.date_from is not None or filters.date_to is not None:
        conditions.append(
            FieldCondition(
                key="date",
                range=DatetimeRange(
                    gte=day_start(filters.date_from) if filters.date_from is not None else None,
                    lt=(
                        day_start(filters.date_to + timedelta(days=1))
                        if filters.date_to is not None
                        else None
                    ),
                ),
            )
        )
    if filters.source is not None:
        conditions.append(FieldCondition(key="source", match=MatchValue(value=filters.source)))
    if filters.numerology_value is not None:
        conditions.append(
            FieldCondition(key="numerology_value", match=MatchValue(value=filters.numerology_value))
        )
    if filters.master_number is not None:
        conditions.append(
            FieldCondition(key="master_number", match=MatchValue(value=filters.master_number))
        )
    if not conditions:
        return Filter()
    return Filter(must=conditions)
