"""Every prompt the agents send, in one place.

The instructions are written in English — models follow English instructions most reliably — while
the prose a person reads (a pattern's interpretation, the forecast, its advice and warnings) is
generated in Russian, the language of the product's documented example output.

Changing one of these constants means updating ``docs/PROMPTS.md`` in the same commit (AGENTS.md).
"""

from __future__ import annotations

from collections.abc import Sequence

from numenews.models import NewsItem

EXTRACT_INSTRUCTIONS = """\
You read one news text and report the numbers and symbols it contains. You do not interpret them.

Numbers:
- Report every integer written in the text: digits ("12 people"), spelled-out numerals
  ("three ministers") and the components of a date ("21 September 2026" gives 21 and 2026).
- Report the numbers in the order they appear, and report each number once.
- Never compute, reduce, sum or otherwise transform a number: report what the text says.
- Never report a number that is not in the text.

Symbols:
- Report the notable symbols of the text: abbreviations and tickers ("AI", "EU", "NASA"), currency
  and other signs ("$", "€", "⚠"), and every symbol of a watchlist given with the text.
- Report a symbol exactly as it appears in the text, and report each symbol once.
- Never report a symbol that is not in the text.
"""


def build_extract_prompt(text: str, symbols: Sequence[str] = ()) -> str:
    """Return the prompt for one text, with an optional symbol watchlist.

    The watchlist is a caller-owned vocabulary (phase 1.6's ``extract_symbols`` needs one as well),
    so the regex fallback and the model look for the same symbols.
    """
    if not symbols:
        return f"Text:\n{text}"
    watchlist = ", ".join(symbols)
    return f"Watchlist symbols: {watchlist}\n\nText:\n{text}"


PATTERN_INSTRUCTIONS = """\
You look for numerological and symbolic connections among a set of news items. Every item comes with
an id, its date, its source, its title, its text, the numbers it contains and its reduced
numerological value (a number from 1 to 9, or the master number 11, 22 or 33).

Report a connection for each of these kinds, when the items justify it:
- "repetition": the same number appears in several items.
- "master": a master number (11, 22 or 33) is involved.
- "resonance": two numbers or dates reduce to the same value.
- "symbol": the same symbol, name or place recurs.
- "hidden": a connection the number rules above do not explain.

Rules:
- Every pattern must cite the ids of the items it connects, copied exactly from the input. Never
  invent an id, and never report a connection you cannot point at in the items.
- "numbers" lists the numbers the connection rests on, most important first.
- "strength" is your confidence from 0.0 (a guess) to 1.0 (the items state it plainly).
- "interpretation" is one or two sentences in Russian explaining the connection.
- Report each connection once; an empty list is a valid answer when nothing connects.
"""

#: How much of one news item's text the pattern prompt shows, in characters.
PATTERN_TEXT_LIMIT = 1000


def _news_block(index: int, item: NewsItem) -> str:
    """Render one news item for the pattern prompt."""
    numbers = ", ".join(str(number) for number in item.numbers) or "none"
    value = item.numerology_value if item.numerology_value is not None else "not computed"
    text = item.text[:PATTERN_TEXT_LIMIT]
    return (
        f"{index}. id: {item.id.root}\n"
        f"   date: {item.date.isoformat()} · source: {item.source} · numerology_value: {value}\n"
        f"   title: {item.title}\n"
        f"   numbers: {numbers}\n"
        f"   text: {text}"
    )


def build_pattern_prompt(news: Sequence[NewsItem]) -> str:
    """Return the prompt listing every item the pattern agent has to connect."""
    blocks = "\n\n".join(_news_block(index, item) for index, item in enumerate(news, start=1))
    return f"News items to analyse:\n\n{blocks}"
