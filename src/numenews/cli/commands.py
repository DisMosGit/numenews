"""The command bodies: one async function per CLI command, over the application context.

A command body is a plain coroutine rather than a Typer callback, for the same reason the MCP tools
are plain functions: the interesting work is ``AppContext`` plus one pipeline or vector call, and
keeping it free of the parser means a test drives it without a subprocess, a shell or a terminal.
:mod:`numenews.cli.main` is the thin Typer layer that parses arguments, runs the body and prints the
model it returned.

The commands mirror the MCP tools where a tool exists (``today`` and ``forecast`` over
``Pipeline``/``build_forecast``, ``history`` over ``get_history``, ``search`` over ``query_qdrant``,
``patterns`` over the ``patterns`` collection), which is what ``docs/ARCHITECTURE.md`` means by "one
pipeline, two interfaces".
"""

from __future__ import annotations

from numenews.cli.dates import parse_day
from numenews.mcp.context import AppContext
from numenews.models import DateRange, Forecast, Topic
from numenews.pipeline import window_start


async def today(context: AppContext, *, topic: str) -> Forecast:
    """Ingest the topic's news window and return today's reading.

    Roadmap 7.3 is "ingest + analyze + forecast": the news of the sliding window is fetched and
    stored first, so the reading is built from what is actually in the store, and
    :meth:`~numenews.pipeline.pipeline.Pipeline.forecast` then derives the window's patterns and
    writes the day's reading. The analyze step is not called separately — the forecast step runs it
    over the same window items (``rerun_analysis=True``), and calling both would pay for one model
    run twice.

    The day and the window come from the pipeline's clock and ``window_days``, so a replayed day is
    a matter of the injected clock, not of this function.

    Args:
        context: The application context; its pipeline is built on first use.
        topic: What to search the configured news feeds for.

    Returns:
        The day's reading, as stored — the same object a later call answers from the cache.
    """
    pipeline = await context.pipeline()
    day = pipeline.clock.now().date()
    date_range = DateRange(start=window_start(day, pipeline.window_days), end=day)
    await pipeline.ingest(Topic(query=topic), date_range)
    return await pipeline.forecast(day)


async def forecast(context: AppContext, *, day: str) -> Forecast:
    """Return the reading for ``day``, read from storage when that day was already handled.

    The ``--date`` grammar (``YYYY-MM-DD``, ``today``, ``tomorrow``, ``yesterday``, ``+Nd``,
    ``-Nd``) is resolved against the pipeline's clock, which is also the day the pipeline itself
    would use, so ``--date tomorrow`` and a replayed run agree on which day they mean.

    Unlike :func:`today`, this command does not fetch news: it answers the question "what is stored
    about this day", so running it twice costs nothing after the first.

    Args:
        context: The application context; its pipeline is built on first use.
        day: The raw ``--date`` argument.

    Returns:
        The reading for the resolved day, as stored.
    """
    pipeline = await context.pipeline()
    return await pipeline.forecast(parse_day(day, today=pipeline.clock.now().date()))


__all__ = ["forecast", "today"]
