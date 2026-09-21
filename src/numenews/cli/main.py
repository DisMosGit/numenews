"""The Typer application: one command per one-shot operation, JSON on stdout.

The CLI is the second interface over the same pipeline as the MCP server (phase 6) and stays just as
thin: a command parses its arguments, builds the application context (:class:`AppContext`, reused
from ``numenews.mcp`` so both interfaces share one lazy container), calls one pipeline or vector
operation, and prints the resulting model. Nothing here does numerology, storage or HTTP.

``main`` is the group callback: it configures logging for every invocation and stores the two things
every command needs — the settings and the ``--pretty`` flag — on the Typer context. The command
bodies themselves live in :mod:`numenews.cli.commands` as async functions over ``AppContext``, which
is what makes them testable without a subprocess.

Reference: ``ROADMAP.md`` phase 7, ``docs/USER_FLOW.md`` and ADR 0005/0006.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

import typer

import numenews
from numenews.cli.output import print_json
from numenews.cli.schemas import NotImplementedReport, VersionInfo
from numenews.config import Settings, get_settings
from numenews.logging import configure_logging

app = typer.Typer(
    name="numenews",
    help="A numerological reading of the news: one command per run, JSON on stdout.",
    no_args_is_help=True,
    add_completion=False,
)


@dataclass(frozen=True)
class CliState:
    """What the group callback hands every command: the configuration and the output flag.

    A frozen dataclass rather than the settings themselves, because ``--pretty`` is a property of
    this invocation and not of the configuration; the commands stay decoupled from how the flag
    reached them.
    """

    settings: Settings
    pretty: bool


def state_of(ctx: typer.Context) -> CliState:
    """Return the state the group callback stored on ``ctx``.

    Typer keeps ``ctx.obj`` untyped, so the cast is the one place that knows what the callback put
    there; every command starts here.
    """
    return cast("CliState", ctx.obj)


def _version_callback(value: bool) -> None:
    """Print the version as JSON and exit, before any command runs.

    ``--version`` answers with a document like every other output (ADR 0005), in the compact form,
    so it can be piped into ``jq`` like the rest of the CLI.
    """
    if value:
        print_json(VersionInfo(name="numenews", version=numenews.__version__), pretty=False)
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the package version as JSON and exit.",
        ),
    ] = False,
    pretty: Annotated[
        bool,
        typer.Option("--pretty/--no-pretty", help="Indent the JSON payload (default)."),
    ] = True,
) -> None:
    """Read the news numerologically, once per invocation."""
    configure_logging()
    ctx.obj = CliState(settings=get_settings(), pretty=pretty)


@app.command()
def today(ctx: typer.Context) -> None:
    """Numerological reading of today's news (placeholder until ROADMAP.md 7.3)."""
    print_json(
        NotImplementedReport(
            command="numenews today",
            status="not_implemented",
            phase=7,
            message="The one-shot commands land in ROADMAP.md phase 7.",
        ),
        pretty=state_of(ctx).pretty,
    )
