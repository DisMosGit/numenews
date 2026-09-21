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


class ExtractionDraft(BaseModel):
    """Numbers and symbols a model read out of one text.

    ``numbers`` are the integers explicitly mentioned — including the digits of a date and
    spelled-out numerals; ``symbols`` are the notable symbols, tickers, emoji or watchlist entries
    present in the text. Duplicates are removed by the caller, not by the prompt.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    numbers: list[int] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
