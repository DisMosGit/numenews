"""The CLI's output models: what a command answers with, in JSON.

The commands of roadmap 7.3-7.7 answer with a domain model where one exists (``Forecast``,
``CollectionQueryResult``) and with a small report model where the answer is a collection plus the
arguments that produced it (``HistoryResult``, ``PatternsResult``). A failure answers with
``ErrorReport``. Every one of them is a Pydantic model, because
:func:`~numenews.cli.output.print_json` serializes models and ``AGENTS.md`` keeps dicts out of the
boundaries.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numenews.models import DayActivationCount, NumberActivation, Pattern, PatternType


class VersionInfo(BaseModel):
    """What ``numenews --version`` prints: the package name and its version, as JSON."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


class HistoryResult(BaseModel):
    """The activations of one number inside a window, with the question that produced them.

    A list alone would leave the caller guessing which number and window it belongs to, so the
    arguments are echoed back the way ``CollectionQueryResult`` echoes its own. ``activations`` is
    newest first, as :func:`numenews.vector.get_history` returns them, and ``by_day`` is the same
    rows folded into the per-day frequency of roadmap 8.2 (``activation_frequency``), newest day
    first — so a caller that only wants the shape of the period does not have to count.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    days: int
    activations: tuple[NumberActivation, ...] = ()
    by_day: tuple[DayActivationCount, ...] = ()


class ErrorReport(BaseModel):
    """What a command prints when an expected domain failure stopped it.

    The roadmap's error contract for the CLI (ADR 0005): an expected failure — an unreachable store,
    an unconfigured model endpoint, a spent retry — is an answer too, so stdout stays one JSON
    document and the process exits ``1``. ``kind`` carries the exception class name, so a script can
    branch on the failure without parsing the message.
    """

    model_config = ConfigDict(frozen=True)

    error: str
    kind: str


class PatternsResult(BaseModel):
    """The stored patterns that matched, with the filters that selected them.

    ``patterns`` is already ordered by ``strength`` descending and then by discovery time, as
    :func:`numenews.vector.read_patterns` returns it. The filters are echoed back for the same
    reason :class:`HistoryResult` echoes its arguments: the answer should carry its question.
    """

    model_config = ConfigDict(frozen=True)

    pattern_type: PatternType | None = None
    min_strength: float | None = None
    patterns: tuple[Pattern, ...] = ()


__all__ = ["ErrorReport", "HistoryResult", "PatternsResult", "VersionInfo"]
