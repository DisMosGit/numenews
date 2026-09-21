"""ForecastAgent: the day's reading in prose.

The agent writes text; everything else in a :class:`~numenews.models.Forecast` is decided by the
layers that own it — the date and its numerological values come from ``numenews.numerology`` through
the pipeline (AGENTS.md keeps numerology out of the agents), and the patterns come from phase 4.3 or
from Qdrant. The recent activations are an input too: the pipeline reads them from
``number_history`` over its memory window (``history_days``, thirty days by default — phase 8.3) and
hands them over, so this layer stays free of storage.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from numenews.agents.errors import AgentExecutionError
from numenews.agents.llm import build_llm_model
from numenews.agents.prompts import FORECAST_INSTRUCTIONS, build_forecast_prompt
from numenews.agents.schemas import ForecastDraft
from numenews.config import Settings
from numenews.models import Forecast, NumberActivation, Pattern

#: Name the agent reports in logs and in :class:`AgentExecutionError`.
AGENT_NAME = "build_forecast"


class ForecastAgent:
    """Builds the daily reading from the day's numbers, patterns and recent activations.

    Args:
        model: The model to run. Omitted in the application — the one from
            :func:`~numenews.agents.llm.build_llm_model` is used — and passed explicitly by tests.
        settings: Settings used to build the default model when ``model`` is omitted.
    """

    def __init__(self, model: Model | None = None, *, settings: Settings | None = None) -> None:
        self._agent: Agent[None, ForecastDraft] = Agent(
            model if model is not None else build_llm_model(settings),
            output_type=ForecastDraft,
            instructions=FORECAST_INSTRUCTIONS,
            name=AGENT_NAME,
            retries={"output": 2},
        )

    async def forecast(
        self,
        *,
        date: date,
        dominant_number: int,
        master_active: bool,
        patterns: Sequence[Pattern] = (),
        history: Sequence[NumberActivation] = (),
    ) -> Forecast:
        """Return the reading for ``date``.

        Args:
            date: The day being read.
            dominant_number: The day's reduced number, from ``numerology``.
            master_active: Whether a master number (11, 22 or 33) participates in the day.
            patterns: The patterns the reading should rest on (phase 4.3 or Qdrant).
            history: Recent number activations, newest first, as the pipeline's memory window read
                them (``number_history``, phase 3.7; window of phase 8.3).

        Returns:
            A :class:`~numenews.models.Forecast` carrying the given facts and the model's prose.

        Raises:
            AgentExecutionError: If the model run failed or its output never validated.
        """
        prompt = build_forecast_prompt(
            date=date,
            dominant_number=dominant_number,
            master_active=master_active,
            patterns=patterns,
            history=history,
        )
        try:
            result = await self._agent.run(prompt)
        except AgentRunError as error:
            raise AgentExecutionError(AGENT_NAME, str(error)) from error

        draft = result.output
        return Forecast(
            date=date,
            dominant_number=dominant_number,
            master_active=master_active,
            patterns=tuple(patterns),
            forecast=draft.forecast,
            advice=draft.advice,
            warnings=tuple(draft.warnings),
        )
