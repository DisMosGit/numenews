"""The *draft* schemas the language model is asked to fill.

A draft carries only what a model can honestly know about its input: the numbers and symbols it
found, the connections it sees, the prose it wrote. Everything else in the domain models of
``numenews.models`` is ours, not the model's — provenance (``ExtractedNumbers.sources``), identity
(``Pattern.id``, ``Pattern.discovered_at``) and the numerological values the pure layer computed
(``Forecast.date``, ``dominant_number``, ``master_active``, ``patterns``). Asking the model for
those would either invite invention or force the prompt to echo values we already have.

The fields are shaped like the JSON a model emits — arrays and strings, not the domain models'
tuples and ``RootModel[UUID]`` wrappers. ``pydantic-ai`` validates tool arguments in Python mode,
where a strict ``tuple`` refuses a list and a strict ``UUID`` refuses a string, so a draft that
mirrored the domain types exactly would reject every well-formed answer. Identity strings are parsed
by the agent when the domain object is assembled.

Each draft is frozen and strict like the domain models: a draft never changes, and a value is never
coerced (a model that writes ``"7"`` where an integer belongs is asked again, not guessed at).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from numenews.models import PatternType


class ExtractionDraft(BaseModel):
    """Numbers and symbols a model read out of one text.

    ``numbers`` are the integers explicitly mentioned — including the digits of a date and
    spelled-out numerals; ``symbols`` are the notable symbols, tickers, emoji or watchlist entries
    present in the text. Duplicates are removed by the caller, not by the prompt.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    numbers: list[int] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class PatternDraft(BaseModel):
    """A connection between news items, as the model sees it.

    ``news_ids`` are UUID strings copied from the analysed items — a ``str`` and not
    :class:`~numenews.models.NewsId`, for the validation-mode reason in the module docstring; the
    agent parses each one and keeps only the ids it actually received. ``strength`` is the model's
    confidence and is bounded here, so a value outside ``[0, 1]`` is rejected at the boundary rather
    than stored. ``interpretation`` is written in Russian (see ``docs/PROMPTS.md``).
    """

    model_config = ConfigDict(frozen=True, strict=True)

    type: PatternType
    numbers: list[int] = Field(default_factory=list)
    news_ids: list[str]
    strength: float = Field(ge=0.0, le=1.0)
    interpretation: str


class ForecastDraft(BaseModel):
    """The prose of one day's reading.

    The day, its dominant number, whether a master number is active and the patterns it was built
    from are *not* here: they come from the pure numerology layer and from Qdrant, and the agent
    receives them as input. ``forecast`` and ``advice`` may not be blank — a reading that says
    nothing is a failed run to retry, not a result. The text is written in Russian.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    forecast: str = Field(min_length=1)
    advice: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class DigestDraft(BaseModel):
    """The summary of a stretch of older news.

    Only the prose: the period it covers is the caller's fact (the range of the items that were
    passed), and the numbers it rests on are read back from those items by the layer that stores the
    digest — a model asked to repeat them would only have another chance to get one wrong. The
    summary may not be blank, for the same reason as ``ForecastDraft``'s fields, and is written in
    Russian.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    summary: str = Field(min_length=1)
