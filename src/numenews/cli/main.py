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

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Literal, cast

import typer
from pydantic import BaseModel

import numenews
from numenews.cli import commands
from numenews.cli.output import print_json
from numenews.cli.schemas import ErrorReport, VersionInfo
from numenews.config import Settings, get_settings
from numenews.logging import (
    bind_request_context,
    configure_logging,
    get_logger,
    new_request_id,
)
from numenews.mcp.context import AppContext
from numenews.mcp.errors import DOMAIN_ERRORS

logger = get_logger("numenews.cli")

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


def build_context(settings: Settings) -> AppContext:
    """Return the application context one invocation uses.

    The CLI shares ``AppContext`` with the MCP server instead of growing a second container: it is
    already the lazy factory for the store, the pipeline and the news client, and both interfaces
    want exactly that. A test replaces this function to hand a command an in-memory store and
    scripted agents, which is why it is a module-level function and not an inline call.
    """
    return AppContext(settings)


def run_command[ResultT: BaseModel](
    ctx: typer.Context,
    work: Callable[[AppContext], Awaitable[ResultT]],
) -> None:
    """Run one async command body, print its model, and turn an expected failure into JSON.

    One event loop per invocation is what "one-shot" means: the process answers one question and
    exits, so ``asyncio.run`` is the right driver rather than a long-lived loop.

    An expected domain failure (``DOMAIN_ERRORS``: the store is down, the model endpoint is not
    configured, a step spent its retry) is an answer too — it is printed as an ``ErrorReport`` on
    stdout and exits ``1``, so a script can read the failure as JSON. Anything else is a defect in
    this code base and stays loud: it propagates to the Click error handler with a traceback on
    stderr and an empty stdout, the same policy the MCP tools follow (phase 6).
    """
    state = state_of(ctx)
    command = ctx.command.name or "numenews"

    async def invoke() -> ResultT:
        context = build_context(state.settings)
        try:
            return await work(context)
        finally:
            await context.aclose()

    try:
        result = asyncio.run(invoke())
    except DOMAIN_ERRORS as error:
        logger.warning(
            "cli.command.failed",
            command=command,
            kind=type(error).__name__,
            error=str(error),
        )
        print_json(ErrorReport(kind=type(error).__name__, error=str(error)), pretty=state.pretty)
        raise typer.Exit(code=1) from error
    logger.info("cli.command.complete", command=command)
    print_json(result, pretty=state.pretty)


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
    bind_request_context(request_id=new_request_id())
    logger.info("cli.invoked", pretty=pretty)
    ctx.obj = CliState(settings=get_settings(), pretty=pretty)


@app.command()
def today(
    ctx: typer.Context,
    topic: Annotated[
        str,
        typer.Option("--topic", help="What to search the configured news feeds for."),
    ] = "politics",
) -> None:
    """Ingest today's news window and print the day's numerological reading.

    Fetches the topic's news for the last seven days, stores what the extraction reads out of it,
    and answers with the day's ``Forecast``: its dominant number, whether a master number is active,
    the patterns among the window's items, the prose reading and the advice. Needs Qdrant and an
    LLM endpoint; news sources without a key are simply not queried.
    """
    run_command(ctx, lambda context: commands.today(context, topic=topic))


@app.command()
def forecast(
    ctx: typer.Context,
    day: Annotated[
        str,
        typer.Option(
            "--date",
            help="Day to read: YYYY-MM-DD, today, tomorrow, yesterday, +Nd or -Nd.",
        ),
    ] = "today",
) -> None:
    """Print the reading for a calendar day, from storage when that day was already read.

    Unlike ``today`` this command fetches nothing: it reads the stored news window, runs the model
    only when the day has no stored reading, and answers with the day's ``Forecast``. Needs Qdrant
    and an LLM endpoint.
    """
    run_command(ctx, lambda context: commands.forecast(context, day=day))


@app.command()
def history(
    ctx: typer.Context,
    number: Annotated[int, typer.Option("--number", help="The number whose activations to read.")],
    days: Annotated[
        int,
        typer.Option("--days", min=1, max=365, help="Length of the window in days, ending today."),
    ] = 30,
) -> None:
    """Print when a number was activated in the news, newest first, inside a recent window.

    One entry per ``(news item, number)`` pair a previous ingest stored: the publication day, the
    item's id and the sentence the number was read in. ``--days`` ends today and includes it, so
    ``--days 1`` is today. Needs Qdrant only.
    """
    run_command(ctx, lambda context: commands.history(context, number=number, days=days))


@app.command()
def search(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="What to look for, in natural language."),
    ],
    collection: Annotated[
        # Spelled out instead of using ``CollectionName``: Typer does not resolve a PEP 695 type
        # alias, and ``commands.search`` takes the domain alias, so mypy is what keeps the two in
        # step.
        Literal["news", "patterns"],
        typer.Option("--collection", help="Which collection to search."),
    ] = "news",
    limit: Annotated[int, typer.Option("--limit", min=1, max=50, help="Maximum results.")] = 10,
) -> None:
    """Search the stored news or patterns by meaning, best match first.

    ``--collection news`` (the default) runs the same hybrid search as the MCP ``query_qdrant``
    tool over stored articles; ``--collection patterns`` finds saved pattern interpretations. Needs
    Qdrant only: the query is embedded locally and no model is called.
    """
    run_command(
        ctx,
        lambda context: commands.search(context, query=query, collection=collection, limit=limit),
    )


@app.command()
def patterns(
    ctx: typer.Context,
    pattern_type: Annotated[
        # Spelled out instead of using ``PatternType`` for the same reason as ``--collection``:
        # Typer does not resolve a PEP 695 alias, and ``commands.patterns`` takes the domain alias.
        Literal["resonance", "repetition", "master", "symbol", "hidden"] | None,
        typer.Option("--type", help="Keep only patterns of this kind."),
    ] = None,
    min_strength: Annotated[
        float | None,
        typer.Option(
            "--min-strength",
            min=0.0,
            max=1.0,
            help="Keep only patterns at least this strong (0 to 1).",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, max=200, help="Maximum number of patterns."),
    ] = 50,
) -> None:
    """List the patterns already stored, strongest first, optionally filtered.

    A pattern is stored by an ``analyze`` step or by the MCP ``save_pattern`` tool; this command
    reads those back by the two indexed fields — ``--type`` and ``--min-strength`` — instead of
    searching them by meaning (that is ``search --collection patterns``). Needs Qdrant only.
    """
    run_command(
        ctx,
        lambda context: commands.patterns(
            context,
            pattern_type=pattern_type,
            min_strength=min_strength,
            limit=limit,
        ),
    )
