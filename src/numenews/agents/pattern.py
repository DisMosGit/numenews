"""PatternAgent: connections among a set of news items.

The model proposes the connections; this module decides what a connection *is*. A draft becomes a
:class:`~numenews.models.Pattern` only if it cites ids the caller actually passed, and the pattern's
identity is derived from its content with ``uuid5`` — the same determinism as
:func:`numenews.news.items.news_id` — so analysing the same items twice overwrites the same Qdrant
point instead of inventing a new one (phase 3.5 saves a pattern under its own id).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from numenews.agents.errors import AgentExecutionError
from numenews.agents.llm import build_llm_model
from numenews.agents.prompts import PATTERN_INSTRUCTIONS, build_pattern_prompt
from numenews.agents.schemas import PatternDraft
from numenews.config import Settings
from numenews.models import NewsId, NewsItem, Pattern, PatternId, PatternType

#: Name the agent reports in logs and in :class:`AgentExecutionError`.
AGENT_NAME = "find_patterns"


def _existing_ids(raw_ids: Iterable[str], known: frozenset[UUID]) -> list[NewsId]:
    """Return the ids of ``raw_ids`` that name one of ``known`` items, without duplicates.

    A model occasionally mangles or invents a UUID; a connection to an item that is not in front
    of the model is not a connection this layer can store, so the bad id is dropped rather than
    trusted.
    """
    found: list[NewsId] = []
    for raw in raw_ids:
        try:
            value = UUID(raw)
        except ValueError:
            continue
        if value in known:
            found.append(NewsId(value))
    return list(dict.fromkeys(found))


def pattern_id(
    pattern_type: PatternType,
    numbers: Sequence[int],
    news_ids: Sequence[NewsId],
) -> PatternId:
    """Return the deterministic id of a pattern found over ``news_ids``.

    Derived from the pattern's own content — its kind, its numbers and the (sorted) items it links —
    so the same connection found twice is one pattern. ``discovered_at`` is *not* part of the key:
    it describes the moment ``save_pattern`` wrote the point, and phase 3.5 keeps the first one.
    """
    key = "|".join(
        (
            pattern_type,
            ",".join(str(number) for number in sorted(numbers)),
            ",".join(sorted(str(news_id.root) for news_id in news_ids)),
        )
    )
    return PatternId(uuid5(NAMESPACE_URL, key))


class PatternAgent:
    """Finds the connections among a set of news items.

    Args:
        model: The model to run. Omitted in the application — the one from
            :func:`~numenews.agents.llm.build_llm_model` is used — and passed explicitly by tests.
        settings: Settings used to build the default model when ``model`` is omitted.
    """

    def __init__(self, model: Model | None = None, *, settings: Settings | None = None) -> None:
        self._agent: Agent[None, list[PatternDraft]] = Agent(
            model if model is not None else build_llm_model(settings),
            output_type=list[PatternDraft],
            instructions=PATTERN_INSTRUCTIONS,
            name=AGENT_NAME,
            retries={"output": 2},
        )

    async def find_patterns(self, news: Sequence[NewsItem]) -> list[Pattern]:
        """Return the patterns found among ``news``.

        Args:
            news: The items to connect, typically one day's ingested news.

        Returns:
            The patterns, in the order the model reported them, each with a deterministic id and
            with ``discovered_at`` left unset for phase 3.5's ``save_pattern`` to stamp.

        Raises:
            AgentExecutionError: If the model run failed or its output never validated. An empty
                list is a valid answer, so a caller can tell "nothing connects" from "no answer".
        """
        known = frozenset(item.id.root for item in news)
        if not known:
            return []

        try:
            result = await self._agent.run(build_pattern_prompt(news))
        except AgentRunError as error:
            raise AgentExecutionError(AGENT_NAME, str(error)) from error

        patterns: list[Pattern] = []
        for draft in result.output:
            news_ids = _existing_ids(draft.news_ids, known)
            if not news_ids:
                continue
            numbers = tuple(dict.fromkeys(draft.numbers))
            patterns.append(
                Pattern(
                    id=pattern_id(draft.type, numbers, news_ids),
                    type=draft.type,
                    numbers=numbers,
                    news_ids=tuple(news_ids),
                    strength=draft.strength,
                    interpretation=draft.interpretation,
                )
            )
        return patterns
