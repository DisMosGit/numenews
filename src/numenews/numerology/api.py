"""The public entry point of the numerology layer."""

from __future__ import annotations

from numenews.models.results import NumerologyResult
from numenews.numerology.gematria import gematria_simple
from numenews.numerology.master import is_master
from numenews.numerology.reduction import reduce_number, reduction_steps


def compute_numerology(text: str) -> NumerologyResult:
    """Read a text: its letter sum, the reduced value, and the steps between them.

    This is the one function the interfaces above call. The MCP tool of phase 6.4 returns its
    result unchanged and the CLI prints it as JSON, so the shape of
    :class:`~numenews.models.results.NumerologyResult` is the contract.

    Extraction is deliberately *not* part of it. Finding numbers and dates in the text is the
    agent's job with ``extract_*_regex`` as its fallback (phase 4.2); a reading of the text's
    letters does not depend on what those regexes found, and mixing the two would make one result
    answer two questions.

    A text without a mapped letter is not an error — a news title may be a bare number or an emoji,
    and the pipeline should not fall over it. It yields ``gematria == value == 0`` and a breakdown
    that says so.

    Args:
        text: The text to read, in any language whose letters the value tables know.

    Returns:
        The reading, with the rendered calculation in ``breakdown``.

    Examples:
        ``compute_numerology("Sun rises")`` sums the letters to ``124`` and reduces to ``7``;
        ``compute_numerology("k")`` stops at the master number ``11``.
    """
    gematria = gematria_simple(text)

    if gematria == 0:
        return NumerologyResult(
            text=text,
            gematria=0,
            value=0,
            is_master=False,
            breakdown=("no letters to sum",),
        )

    value = reduce_number(gematria)

    return NumerologyResult(
        text=text,
        gematria=gematria,
        value=value,
        is_master=is_master(value),
        breakdown=(f"gematria_simple = {gematria}", *reduction_steps(gematria)),
    )
