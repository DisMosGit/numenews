"""Patterns found across news items."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from numenews.models.ids import NewsId, PatternId

# The kinds of connection a pattern can describe: dates that reduce to the same value, a number
# repeating across items, a master number (11/22/33), a symbol that returns, or a link the pattern
# agent found that the number rules do not explain. New members are additive.
type PatternType = Literal["resonance", "repetition", "master", "symbol", "hidden"]


class Pattern(BaseModel):
    """A connection between news items with a confidence.

    ``strength`` is bounded to ``[0, 1]`` here rather than in the agent, so a model output that
    leaves the range is rejected at the boundary (phase 4).

    ``discovered_at`` is when the pattern was written to Qdrant and is indexed there. It is optional
    because the pattern agent (4.3) describes a connection, not a moment: ``save_pattern`` stamps an
    unstamped pattern with the current UTC time, and a pattern that already carries a timestamp —
    read back from storage, or built by a test — keeps it.
    """

    model_config = ConfigDict(frozen=True, strict=True)

    id: PatternId
    type: PatternType
    numbers: tuple[int, ...]
    news_ids: tuple[NewsId, ...]
    strength: float = Field(ge=0.0, le=1.0)
    interpretation: str
    discovered_at: datetime | None = None
