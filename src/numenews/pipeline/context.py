"""Context management: what the agents see, and what is compressed instead.

One rule lives here (roadmap 5.5). The agents read the *window* — the day being handled and the
``window_days - 1`` days before it — because a reading is about the present. Everything older is not
passed to them at all; it is summarised once into a
:class:`~numenews.models.Digest` and stored, so the project's memory of an earlier stretch is a
sentence rather than a pile of articles.

Two consequences are deliberate. First, the window is the *only* place the seven-day rule is
written: the steps read their news with the same ``start``/``end`` arithmetic that
:func:`partition` uses, so a change here changes both. Second, a digest is never written by an
ingest run — it is written when a caller asks for one, because summarising costs a model call and an
ingest that does not read history should not pay for it.
"""

from __future__ import annotations

from datetime import date, timedelta

from numenews.logging import get_logger
from numenews.models import Digest, NewsItem
from numenews.pipeline.pipeline import Pipeline
from numenews.pipeline.steps import retrying
from numenews.vector import save_digest

logger = get_logger(__name__)


def window_start(end: date, window_days: int) -> date:
    """Return the first day of the window that ends on ``end``.

    ``window_days=7`` and ``end=2026-09-21`` give ``2026-09-15``: the day itself and the six before
    it. This is the one definition of the window, used by both the steps and :func:`partition`.
    """
    return end - timedelta(days=window_days - 1)


def partition(
    news: list[NewsItem], *, end: date, window_days: int
) -> tuple[list[NewsItem], list[NewsItem]]:
    """Split ``news`` into the window's items and the older ones, both oldest first.

    The window is inclusive of ``end``, and an item published *after* ``end`` is not old news and
    not part of the window either — a caller that asks for a replayed day should not summarise the
    future. Such items are left out of both halves and reported by the counts below.

    Args:
        news: The items to split, in any order.
        end: The last day of the window.
        window_days: Length of the window in calendar days.

    Returns:
        ``(recent, older)``: the items inside the window, and the items before it.
    """
    start = window_start(end, window_days)
    recent = sorted(
        (item for item in news if start <= item.date <= end), key=lambda item: item.date
    )
    older = sorted((item for item in news if item.date < start), key=lambda item: item.date)
    logger.debug(
        "pipeline.context.partitioned",
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        recent=len(recent),
        older=len(older),
    )
    return recent, older


async def build_digest(pipeline: Pipeline, news: list[NewsItem]) -> Digest | None:
    """Summarise ``news`` into a digest and store it, or return ``None`` when there is no summary.

    ``None`` is returned for an empty list and for a single item: a digest exists to compress many
    days into one sentence, and "summarise" of one article is the article. The period is the range
    of the items' own days, so a stretch with gaps is labelled by its first and last day.

    Args:
        pipeline: The orchestrator whose summarizer, store and clock are used.
        news: The older items to compress; the order does not matter.

    Returns:
        The stored digest, or ``None`` when two or more items were not given.
    """
    if len(news) < 2:
        return None
    digest = await retrying("summarize_news", lambda: pipeline.summarizer.summarize(news))
    await pipeline.run_blocking(lambda: save_digest(pipeline.store, digest))
    logger.info(
        "pipeline.context.digest",
        period_start=digest.period_start.isoformat(),
        period_end=digest.period_end.isoformat(),
        items=len(news),
    )
    return digest


__all__ = ["build_digest", "partition", "window_start"]
