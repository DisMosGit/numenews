"""ExtractNumbersAgent: the numbers and symbols of one text.

The model runs first, but the deterministic regex pass of phase 1.6 always runs too: a model that is
missing, slow or wrong degrades to ``extract_numbers_regex`` instead of failing the pipeline, which
is the definition of done of ROADMAP 4.2. ``ExtractedNumbers.sources`` records which strategies
contributed, so a reader of the result can tell a model reading from a regex one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from numenews.agents.llm import build_llm_model
from numenews.agents.prompts import EXTRACT_INSTRUCTIONS, build_extract_prompt
from numenews.agents.schemas import ExtractionDraft
from numenews.config import Settings
from numenews.logging import get_logger
from numenews.models import ExtractedNumbers
from numenews.numerology import extract_numbers_regex, extract_symbols

#: Name the agent reports in logs and in :class:`AgentExecutionError`.
AGENT_NAME = "extract_numbers"

logger = get_logger(__name__)


def _unique[ItemT](values: Iterable[ItemT]) -> list[ItemT]:
    """Return ``values`` without duplicates, keeping the first occurrence.

    ``ExtractedNumbers.numbers`` is relied on as unique by the vector layer, which derives one point
    id per ``(news_id, number)`` pair (phase 3.4).
    """
    return list(dict.fromkeys(values))


def _regex_pass(text: str, symbols: Sequence[str]) -> ExtractedNumbers:
    """Return the deterministic reading: regex numbers and the watchlist symbols that occur."""
    return ExtractedNumbers(
        numbers=tuple(_unique(extract_numbers_regex(text))),
        sources=("regex",),
        symbols=tuple(extract_symbols(text, symbols)),
    )


class ExtractNumbersAgent:
    """Reads the numbers and symbols out of one text.

    Args:
        model: The model to run. Omitted in the application — the one from
            :func:`~numenews.agents.llm.build_llm_model` is used — and passed explicitly by tests,
            which run a ``TestModel``/``FunctionModel`` instead of a real endpoint.
        settings: Settings used to build the default model when ``model`` is omitted.
    """

    def __init__(self, model: Model | None = None, *, settings: Settings | None = None) -> None:
        self._agent: Agent[None, ExtractionDraft] = Agent(
            model if model is not None else build_llm_model(settings),
            output_type=ExtractionDraft,
            instructions=EXTRACT_INSTRUCTIONS,
            name=AGENT_NAME,
            retries={"output": 2},
        )

    async def extract(self, text: str, *, symbols: Sequence[str] = ()) -> ExtractedNumbers:
        """Return the numbers and symbols of ``text``.

        The model's reading comes first and the regex pass fills in what it missed; when the model
        fails — transport error, or output that never validated — the regex reading is the result.
        ``sources`` lists the strategies that actually contributed something.

        Args:
            text: The text to read, typically a news item's title and body.
            symbols: Symbols worth looking for, e.g. a watchlist of tickers.
        """
        fallback = _regex_pass(text, symbols)
        try:
            result = await self._agent.run(build_extract_prompt(text, symbols))
        except AgentRunError as error:
            logger.warning(
                "agents.extract.llm_failed",
                agent=AGENT_NAME,
                text_length=len(text),
                error=str(error),
            )
            return fallback

        draft = result.output
        numbers = _unique([*draft.numbers, *fallback.numbers])
        found = _unique([*draft.symbols, *fallback.symbols])
        added = bool(set(fallback.numbers) - set(draft.numbers)) or bool(
            set(fallback.symbols) - set(draft.symbols)
        )
        return ExtractedNumbers(
            numbers=tuple(numbers),
            sources=("llm", "regex") if added else ("llm",),
            symbols=tuple(found),
        )
