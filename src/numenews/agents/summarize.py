"""SummarizeAgent: the news outside the window, compressed into one digest.

The sliding window of roadmap 5.5 keeps the recent days raw for the pattern and forecast agents;
everything older is summarised once — and only when the caller asks for it — so a long-running
installation does not have to carry every article into every prompt.

What the model contributes is the prose. The period and the reduced values of the digest are facts
about the items and are computed here, not asked for: a model that lists the numbers it saw can
list one that was not there, and the digest's numbers are what a later query filters on.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from numenews.agents.errors import AgentExecutionError
from numenews.agents.llm import build_llm_model
from numenews.agents.prompts import SUMMARIZE_INSTRUCTIONS, build_digest_prompt
from numenews.agents.schemas import DigestDraft
from numenews.config import Settings
from numenews.models import Digest, NewsItem

#: Name the agent reports in logs and in :class:`AgentExecutionError`.
AGENT_NAME = "summarize_news"


def digest_of(news: Sequence[NewsItem], summary: str) -> Digest:
    """Return the digest of ``news``: the period they cover, the summary, and their values.

    The period is the range of the items' own publication days, and ``numbers`` are their reduced
    values in first-seen order without duplicates — the same "what the period was read under" that
    the dominant rule answers for one day.
    """
    ordered = sorted(news, key=lambda item: item.date)
    return Digest(
        period_start=ordered[0].date,
        period_end=ordered[-1].date,
        summary=summary,
        numbers=tuple(
            dict.fromkeys(
                item.numerology_value for item in ordered if item.numerology_value is not None
            )
        ),
    )


class SummarizeAgent:
    """Compresses a set of older news items into one numerological digest.

    Args:
        model: The model to run. Omitted in the application — the one from
            :func:`~numenews.agents.llm.build_llm_model` is used — and passed explicitly by tests.
        settings: Settings used to build the default model when ``model`` is omitted.
    """

    def __init__(self, model: Model | None = None, *, settings: Settings | None = None) -> None:
        self._agent: Agent[None, DigestDraft] = Agent(
            model if model is not None else build_llm_model(settings),
            output_type=DigestDraft,
            instructions=SUMMARIZE_INSTRUCTIONS,
            name=AGENT_NAME,
            retries={"output": 2},
        )

    async def summarize(self, news: Sequence[NewsItem]) -> Digest:
        """Return the digest of ``news``.

        Args:
            news: The items to compress, typically everything older than the sliding window.

        Returns:
            The digest, with the period and the numbers taken from the items.

        Raises:
            ValueError: when ``news`` is empty — an empty digest has no period, and the caller
                decides what an idle stretch means rather than asking the model to summarise
                nothing.
            AgentExecutionError: If the model run failed or its output never validated.
        """
        if not news:
            raise ValueError("summarize expects at least one news item")
        try:
            result = await self._agent.run(build_digest_prompt(news))
        except AgentRunError as error:
            raise AgentExecutionError(AGENT_NAME, str(error)) from error
        return digest_of(news, result.output.summary)
