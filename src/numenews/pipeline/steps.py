"""The step functions the ``Pipeline`` methods delegate to.

Each step is a plain async function over a :class:`~numenews.pipeline.pipeline.Pipeline`, so the
orchestration is testable without constructing a class around a fake and the ``Pipeline`` methods
stay three-line delegations. Every step follows the same shape:

1. run the work inside a :class:`~numenews.pipeline.timings.StepTimer`, which records the monotonic
   duration regardless of outcome;
2. log one ``pipeline.step`` line with the step's counters (roadmap 5.1);
3. put the recorded timing into the returned model, so a caller can report the profile.

Blocking vector calls go through :meth:`Pipeline.run_blocking` (``asyncio.to_thread``); the model
runs are already async. A step that failed logs ``pipeline.step.failed`` and lets the exception out
— the pipeline does not fabricate a result, and phase 6 decides how an MCP tool reports a failure.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import date, timedelta
from functools import partial

from numenews.agents import AgentError
from numenews.logging import get_logger
from numenews.models import (
    DateRange,
    Digest,
    ExtractedNumbers,
    Forecast,
    NewsId,
    NewsItem,
    NumberActivation,
    Pattern,
    Topic,
)
from numenews.numerology import compute_numerology, dominant_number, reduce_date
from numenews.pipeline.errors import PipelineError, PipelineRetryError
from numenews.pipeline.pipeline import Pipeline
from numenews.pipeline.timings import PipelineRun, StepTimer, Timing
from numenews.vector import (
    CollectionNotFoundError,
    create_news_collection,
    get_activations,
    get_forecast,
    get_news_items,
    read_news_range,
    record_activation,
    save_digest,
    save_forecast,
    save_pattern,
    upsert_news,
    upsert_number_patterns,
)

logger = get_logger(__name__)

#: How many attempts a model-backed step gets before its failure is surfaced. One retry absorbs a
#: dropped connection or a single malformed answer; more than one turns a broken endpoint into a
#: long, expensive run.
ATTEMPTS = 2

#: How much of a news item an activation's context keeps, in characters. It is the snippet the
#: ``numbers`` collection embeds and the forecast prompt later shows (``HISTORY_CONTEXT_LIMIT``), so
#: one long article cannot crowd the memory out.
CONTEXT_LIMIT = 160


async def retrying[ResultT](step: str, run: Callable[[], Awaitable[ResultT]]) -> ResultT:
    """Run ``run`` up to :data:`ATTEMPTS` times, raising :class:`PipelineRetryError` at the end.

    Only agent failures are retried. A ``VectorStoreError`` means the database is gone and a second
    attempt cannot help, and an :class:`PipelineError` is the pipeline's own configuration, never
    worth repeating.
    """
    last: AgentError | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return await run()
        except AgentError as error:
            last = error
            logger.warning(
                "pipeline.step.retry",
                step=step,
                attempt=attempt,
                attempts=ATTEMPTS,
                error=str(error),
            )
    if last is None:  # pragma: no cover
        raise PipelineError(f"{step} was never attempted")
    raise PipelineRetryError(step, str(last))


def log_step(timer: StepTimer, **counters: object) -> None:
    """Write the one log line a finished step owes roadmap 5.1.

    ``failed`` decides the level: a step that raised is the interesting one, so it is a warning with
    the same counters, and the exception itself is logged by the caller's traceback.
    """
    timing = timer.timing
    duration_ms = round(timing.duration_seconds * 1000, 3) if timing is not None else None
    if timer.failed:
        logger.warning("pipeline.step.failed", step=timer.step, duration_ms=duration_ms, **counters)
        return
    logger.info("pipeline.step", step=timer.step, duration_ms=duration_ms, **counters)


def timings(*taken: Timing | None) -> tuple[Timing, ...]:
    """Return the recorded timings, in step order, dropping the ones a step did not reach."""
    return tuple(timing for timing in taken if timing is not None)


def context_snippet(text: str, number: int) -> str:
    """Return the snippet of ``text`` around the first written form of ``number``.

    The ``context`` of a :class:`~numenews.models.NumberActivation` is what the ``numbers``
    collection embeds, so it has to be a phrase about the world — "eleven ministers resigned" — and
    not the whole article or an empty string. The snippet runs from the start of the sentence that
    contains the number, or from the beginning of the text when the number is in its first sentence,
    and is cut to :data:`CONTEXT_LIMIT` characters. A number that is not written in the text (the
    model read "eleven" where the regex read nothing) falls back to the opening of the text, which
    still says what the article is about.

    Args:
        text: The item's text.
        number: The value whose mention should be found.

    Returns:
        A non-empty snippet: whitespace-collapsed, cut to :data:`CONTEXT_LIMIT` characters.
    """
    collapsed = " ".join(text.split())
    marker = str(number)
    position = collapsed.find(marker)
    if position == -1:
        return collapsed[:CONTEXT_LIMIT] or marker
    sentence_break = max(collapsed.rfind(". ", 0, position), collapsed.rfind("! ", 0, position))
    start = 0 if sentence_break == -1 else sentence_break + 2
    return collapsed[start : start + CONTEXT_LIMIT] or marker


def activate(item: NewsItem, numbers: tuple[int, ...]) -> list[NumberActivation]:
    """Return one :class:`~numenews.models.NumberActivation` per distinct number of ``item``.

    Roadmap 8.1's record: the number, the day the article was published, the item it was read in and
    the snippet around it. One point per ``(news_id, number)`` pair — the vector layer's
    ``activation_point_id`` — so a repeated ingest overwrites its activations instead of piling them
    up. Numbers that are not written in the text still get a context: the fallback of
    :func:`context_snippet` keeps the embedded text non-empty.
    """
    return [
        NumberActivation(
            number=number,
            date=item.date,
            news_id=item.id,
            context=context_snippet(f"{item.title}. {item.text}", number),
        )
        for number in dict.fromkeys(numbers)
    ]


def reading_text(item: NewsItem) -> str:
    """Return the text the day's number is computed from: the headline and the body."""
    return f"{item.title}\n\n{item.text}".strip()


def reduced_value(item: NewsItem) -> int | None:
    """Return the item's reduced value, or ``None`` when there is nothing to read.

    Gematria has no letters to sum in a headline that is only a number or an emoji, and
    ``compute_numerology`` reports that as ``0``. ``None`` is the model's documented "not computed"
    — the payload writes no key at all for it (phase 3.3) — and the two must not be confused.
    """
    value = compute_numerology(reading_text(item)).value
    return value if value > 0 else None


async def ingest(pipeline: Pipeline, topic: Topic, date_range: DateRange) -> PipelineRun:
    """Fetch the news and store everything the extraction step read out of it.

    The chain of roadmap 5.2: ``news`` → ``extract`` → ``compute`` → ``embed``. The last step covers
    the whole write side — the ``news`` collection, the semantic ``numbers`` index and the exact
    ``number_history`` log — because all three are written from the same computed items and a
    profile that split them would report one embedding batch three times.

    Idempotency is by ``news_id``: an item whose point is already stored is skipped before its
    extraction, so a repeated ingest costs no model call and writes nothing while a run whose page
    is only partly known still adds the new articles.

    Args:
        pipeline: The orchestrator whose store, agents and clock the step uses.
        topic: What to search the feeds for.
        date_range: The inclusive UTC range to ingest.

    Returns:
        The stored items (with their numbers and reduced value), how many activations were written,
        and one timing per step.

    Raises:
        NewsSourceError: when no source is configured at all.
        VectorStoreError: when Qdrant does not answer.
    """
    with StepTimer(pipeline.clock, "news") as news_timer:
        fetched = await pipeline.fetcher(topic, date_range)
    log_step(news_timer, items=len(fetched))

    if fetched:
        # The idempotency check reads the ``news`` collection, and a first run has none yet. The
        # guard is here rather than in the read so an empty page touches the store not at all;
        # ``upsert_news`` would have created the schema a moment later anyway (phase 3.3).
        await pipeline.run_blocking(lambda: create_news_collection(pipeline.store.client))
    known = await pipeline.run_blocking(
        lambda: get_news_items(pipeline.store, [item.id for item in fetched])
    )
    known_ids = {str(item.id.root) for item in known}
    fresh = [item for item in fetched if str(item.id.root) not in known_ids]
    logger.debug("pipeline.ingest.known", fetched=len(fetched), already_stored=len(known_ids))

    with StepTimer(pipeline.clock, "extract") as extract_timer:
        readings: list[ExtractedNumbers] = []
        for item in fresh:
            readings.append(await pipeline.extract.extract(reading_text(item)))
    log_step(extract_timer, items=len(readings), numbers=sum(len(r.numbers) for r in readings))

    with StepTimer(pipeline.clock, "compute") as compute_timer:
        items = [
            item.model_copy(
                update={"numbers": reading.numbers, "numerology_value": reduced_value(item)}
            )
            for item, reading in zip(fresh, readings, strict=True)
        ]
        activations = [activation for item in items for activation in activate(item, item.numbers)]
    log_step(compute_timer, items=len(items), activations=len(activations))

    with StepTimer(pipeline.clock, "embed") as embed_timer:
        stored = await pipeline.run_blocking(lambda: upsert_news(pipeline.store, items))
        await pipeline.run_blocking(lambda: upsert_number_patterns(pipeline.store, activations))
        for activation in activations:
            await pipeline.run_blocking(partial(record_activation, pipeline.store, activation))
    log_step(embed_timer, items=stored, activations=len(activations))

    logger.info(
        "pipeline.ingest.complete",
        fetched=len(fetched),
        stored=stored,
        activations=len(activations),
    )
    return PipelineRun(
        news=tuple(items),
        activations=len(activations),
        timings=timings(
            news_timer.timing,
            extract_timer.timing,
            compute_timer.timing,
            embed_timer.timing,
        ),
    )


async def analyze(pipeline: Pipeline, news_ids: tuple[NewsId, ...]) -> PipelineRun:
    """Find the patterns among ``news_ids`` and store them.

    Roadmap 5.3 is two steps: ``find`` (the pattern agent of phase 4.3 over the items the ids name)
    and ``store`` (``save_pattern``, which stamps ``discovered_at``). The ids come from a previous
    search or from an ingest run, so a caller that only holds ids — the MCP tool of phase 6.5, the
    CLI of phase 7 — does not have to read the collection itself.

    An unknown or empty ``news_ids`` is not an error: ``find_patterns`` answers an empty list
    without calling the model, and the step stores nothing. A model failure is retried once and then
    surfaces as :class:`PipelineRetryError`, because an empty list must stay distinguishable from
    "the model never answered" (phase 4.3).

    Args:
        pipeline: The orchestrator whose store, pattern agent and clock the step uses.
        news_ids: The items to connect, in the order the prompt should show them.

    Returns:
        The items that were analysed (read back from the store) and the patterns that were saved.

    Raises:
        PipelineRetryError: when the pattern agent failed twice.
        CollectionNotFoundError: when the ``news`` collection was never created.
    """
    with StepTimer(pipeline.clock, "find") as find_timer:
        items = await pipeline.run_blocking(lambda: get_news_items(pipeline.store, news_ids))
        patterns = await retrying("find_patterns", lambda: pipeline.patterns.find_patterns(items))
    log_step(find_timer, items=len(items), patterns=len(patterns))

    with StepTimer(pipeline.clock, "store") as store_timer:
        saved = [
            await pipeline.run_blocking(partial(save_pattern, pipeline.store, pattern))
            for pattern in patterns
        ]
    log_step(store_timer, patterns=len(saved))

    logger.info("pipeline.analyze.complete", items=len(items), patterns=len(saved))
    return PipelineRun(
        news=tuple(items),
        patterns=tuple(saved),
        timings=timings(find_timer.timing, store_timer.timing),
    )


async def forecast(
    pipeline: Pipeline,
    day: date,
    *,
    rerun_analysis: bool = True,
    today: date | None = None,
) -> Forecast:
    """Return the reading for ``day``, from storage when it is already there.

    Roadmap 5.4 in full. A day that is already stored short-circuits everything: the second call
    answers from Qdrant without a model run, which is what ``get_forecast``'s date-derived point id
    was built for (phase 3.6). Otherwise the reading is assembled from four sources:

    * the window of news — ``day`` and the ``window_days - 1`` days before it, read with
      ``read_news_range`` (roadmap 5.5);
    * the patterns among those items, found and stored through the same path as :func:`analyze` —
      skipped when the caller has just run it (``rerun_analysis=False``);
    * the day's ``dominant_number`` and ``master_active`` from the pure rule of
      ``numerology.dominant_number``, with ``reduce_date(day)`` as the fallback for a day with no
      news, because a reading always has a number to rest on;
    * the recent activations of exactly the numbers this day's news carries, so the memory shown to
      the model is evidence for these items and not an unrelated 7 from last week.

    ``analyze`` is re-run rather than reading patterns back by time: ``discovered_at`` records when
    a connection was written, not which day it belongs to, and the deterministic ``PatternId``
    (phase 4.3) makes the second save an overwrite of the same point rather than a duplicate.

    Args:
        pipeline: The orchestrator whose store, agents and clock the step uses.
        day: The calendar day to read.
        rerun_analysis: Whether to derive the day's patterns again (the default) or to trust that
            the caller already ran :func:`analyze` for the same items.
        today: The end of the news window. Defaults to the current UTC day read from the injected
            clock; a caller replaying an old batch passes it explicitly (as in 1.6 and 3.7).

    Returns:
        The reading, as stored — the same object a later call returns from the cache.

    Raises:
        PipelineRetryError: when the pattern or forecast agent failed twice.
        CollectionNotFoundError: when the ``forecasts`` collection was never created.
    """
    with StepTimer(pipeline.clock, "forecast") as cached_timer:
        cached = await _cached_forecast(pipeline, day)
    if cached is not None:
        log_step(cached_timer, cached=True)
        return cached
    log_step(cached_timer, cached=False)

    end = today if today is not None else pipeline.clock.now().date()
    start = end - timedelta(days=pipeline.window_days - 1)
    with StepTimer(pipeline.clock, "window") as window_timer:
        items = await _window_items(pipeline, start, end)
        value = dominant_number(
            [item.numerology_value for item in items if item.numerology_value is not None]
        )
    log_step(window_timer, items=len(items), dominant_number=value.dominant_number)

    patterns: tuple[Pattern, ...] = ()
    if rerun_analysis:
        analysis = await analyze(pipeline, tuple(item.id for item in items))
        patterns = analysis.patterns

    history = await _day_history(pipeline, items, window_days=pipeline.window_days, today=end)

    with StepTimer(pipeline.clock, "write") as write_timer:
        reading = await retrying(
            "build_forecast",
            lambda: pipeline.forecast_agent.forecast(
                date=day,
                dominant_number=value.dominant_number or reduce_date(day),
                master_active=value.is_master,
                patterns=patterns,
                history=history,
            ),
        )
        await pipeline.run_blocking(lambda: save_forecast(pipeline.store, reading))
    log_step(write_timer, patterns=len(patterns), history=len(history))

    logger.info(
        "pipeline.forecast.complete",
        date=day.isoformat(),
        dominant_number=reading.dominant_number,
        master_active=reading.master_active,
    )
    return reading


async def summarize(
    pipeline: Pipeline,
    topic: Topic,
    date_range: DateRange,
    *,
    today: date | None = None,
) -> Digest | None:
    """Ingest ``topic`` for ``date_range`` and compress everything older than the window.

    Roadmap 5.5's public entry: a caller with a month of news to bring in runs this once. The range
    is ingested first (so the window and the older half are both in the store), then the news of the
    range is partitioned: the items inside the window are left alone and the older ones become one
    digest. A range that is entirely inside the window produces no digest, which is the normal
    result of a daily run.

    Args:
        pipeline: The orchestrator whose store, agents and clock the step uses.
        topic: What to fetch.
        date_range: The inclusive UTC range to ingest before summarising.
        today: The last day of the window. Defaults to the current UTC day from the injected clock.
    """
    from numenews.pipeline.context import build_digest, partition

    await ingest(pipeline, topic, date_range)
    end = today if today is not None else pipeline.clock.now().date()
    with StepTimer(pipeline.clock, "summarize") as summarize_timer:
        items = await _window_items(pipeline, date_range.start, date_range.end)
        _recent, older = partition(items, end=end, window_days=pipeline.window_days)
        # The limit bounds the *prompt*, not the period: the digest still covers every older item,
        # while the model is shown the oldest of them. Labelling a digest with a period it only
        # partly read would make the stored memory claim more than it knows.
        digest = await build_digest(pipeline, older[: pipeline.summary_limit])
        if digest is not None and older:
            digest = Digest(
                period_start=older[0].date,
                period_end=older[-1].date,
                summary=digest.summary,
                numbers=tuple(
                    dict.fromkeys(
                        item.numerology_value for item in older if item.numerology_value is not None
                    )
                ),
            )
            await pipeline.run_blocking(lambda: save_digest(pipeline.store, digest))
    log_step(summarize_timer, older=len(older), summarized=digest is not None)
    return digest


async def _cached_forecast(pipeline: Pipeline, day: date) -> Forecast | None:
    """Return the stored reading for ``day``, or ``None`` when there is none.

    ``get_forecast`` keeps "the day was never read" (``None``) apart from "the collection does not
    exist" (``CollectionNotFoundError``), which is the right distinction for a reader of past
    readings. For a *first* forecast the missing collection simply means nothing was read yet, so
    this helper folds that one case into ``None``; a caller that asks about their history wants the
    error, and still gets it from ``get_forecast`` itself (phase 6.7's tool, phase 7's command).
    """
    try:
        return await pipeline.run_blocking(lambda: get_forecast(pipeline.store, day))
    except CollectionNotFoundError:
        return None


async def _window_items(pipeline: Pipeline, start: date, end: date) -> list[NewsItem]:
    """Return the news of the window, or nothing at all when the store has no news yet.

    A first forecast on a fresh store has no ``news`` collection; that is an empty window, not the
    setup error ``read_news_range`` reports to a caller who asked for their data and found none.
    """
    try:
        return await pipeline.run_blocking(lambda: read_news_range(pipeline.store, start, end))
    except CollectionNotFoundError:
        return []


async def _day_history(
    pipeline: Pipeline,
    items: Sequence[NewsItem],
    *,
    window_days: int,
    today: date,
) -> list[NumberActivation]:
    """Return the recent activations of the numbers this day's news carries, newest first.

    Only the numbers of the day are kept: the memory in the prompt is evidence for this reading, and
    an unrelated 7 from last week is not. A day whose news states no number at all asks nothing of
    the history collection, so an empty or uninitialised one cannot fail a reading it does not feed;
    a missing collection is read as "nothing was ever activated", which is what it means here.
    """
    numbers = {number for item in items for number in item.numbers}
    if not numbers:
        return []
    try:
        activations = await pipeline.run_blocking(
            lambda: get_activations(pipeline.store, window_days, today=today)
        )
    except CollectionNotFoundError:
        return []
    return [activation for activation in activations if activation.number in numbers]


__all__ = [
    "ATTEMPTS",
    "CONTEXT_LIMIT",
    "activate",
    "analyze",
    "context_snippet",
    "forecast",
    "ingest",
    "log_step",
    "reading_text",
    "reduced_value",
    "retrying",
    "summarize",
    "timings",
]
