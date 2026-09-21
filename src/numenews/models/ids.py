"""Identity wrappers for the domain models.

Every aggregate gets its own ``RootModel[UUID]`` so that a news id cannot be passed where a pattern
id is expected. The wrappers serialise as bare UUID strings; because the models are strict, a Python
``str`` is not coerced — build them from :class:`uuid.UUID`, or validate a JSON payload with
``model_validate_json`` (that is how the Qdrant payloads are read back in phase 3).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import ConfigDict, RootModel


class NewsId(RootModel[UUID]):
    """Identity of one :class:`~numenews.models.news.NewsItem`."""

    model_config = ConfigDict(frozen=True, strict=True)


class PatternId(RootModel[UUID]):
    """Identity of one :class:`~numenews.models.patterns.Pattern`."""

    model_config = ConfigDict(frozen=True, strict=True)


class ForecastId(RootModel[UUID]):
    """Identity of one :class:`~numenews.models.forecasts.Forecast`."""

    model_config = ConfigDict(frozen=True, strict=True)
