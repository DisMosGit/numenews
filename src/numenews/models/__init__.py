"""Pydantic v2 domain models.

These are the only types that cross module boundaries: the query a caller asks with (topic, date
range), news items, extracted numbers, numerology results, patterns, forecasts and number
activations. Every model is frozen and strict — validation never coerces and an instance never
changes — so a value that crossed a boundary stays what it says it is.

The package imports nothing else from ``numenews``: it is the shared vocabulary the other layers
depend on, never the other way round.
"""

from __future__ import annotations

from numenews.models.forecasts import Forecast
from numenews.models.ids import ForecastId, NewsId, PatternId
from numenews.models.memory import NumberActivation
from numenews.models.news import ExtractedNumbers, NewsItem
from numenews.models.patterns import Pattern, PatternType
from numenews.models.query import DateRange, NewsFilter, Topic
from numenews.models.results import DominantResult, MasterCheckResult, NumerologyResult

__all__ = [
    "DateRange",
    "DominantResult",
    "ExtractedNumbers",
    "Forecast",
    "ForecastId",
    "MasterCheckResult",
    "NewsFilter",
    "NewsId",
    "NewsItem",
    "NumberActivation",
    "NumerologyResult",
    "Pattern",
    "PatternId",
    "PatternType",
    "Topic",
]
