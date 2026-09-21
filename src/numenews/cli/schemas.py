"""The CLI's output models: what a command answers with, in JSON.

The commands of roadmap 7.3-7.7 answer with a domain model where one exists (``Forecast``,
``CollectionQueryResult``) and with a small report model where the answer is a collection plus the
arguments that produced it (``HistoryResult``, ``PatternsResult``). A failure answers with
``ErrorReport``. Every one of them is a Pydantic model, because
:func:`~numenews.cli.output.print_json` serializes models and ``AGENTS.md`` keeps dicts out of the
boundaries.

``NotImplementedReport`` is temporary: it keeps the phase-0 placeholder payload alive for one commit
(roadmap 7.1's stub command) and is deleted in 7.3, when ``today`` becomes real.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VersionInfo(BaseModel):
    """What ``numenews --version`` prints: the package name and its version, as JSON."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: str


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


class NotImplementedReport(BaseModel):
    """The phase-7 placeholder payload, kept until the real ``today`` command replaces it."""

    model_config = ConfigDict(frozen=True)

    command: str
    status: str
    phase: int
    message: str


__all__ = ["ErrorReport", "NotImplementedReport", "VersionInfo"]
