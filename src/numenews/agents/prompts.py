"""Every prompt the agents send, in one place.

The instructions are written in English — models follow English instructions most reliably — while
the prose a person reads (a pattern's interpretation, the forecast, its advice and warnings) is
generated in Russian, the language of the product's documented example output.

Changing one of these constants means updating ``docs/PROMPTS.md`` in the same commit (AGENTS.md).
"""

from __future__ import annotations

from collections.abc import Sequence

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
