"""Every prompt the agents send, in one place.

Each agent has a ``*_RULES`` block, a ``*_FEW_SHOT`` block with one worked example, and the
``*_INSTRUCTIONS`` composed from both — that is what an ``Agent`` is constructed with, while the
``build_*_prompt`` functions render the facts of one call. Keeping the two apart means a prompt can
be read, diffed and snapshot-tested without touching the agent that uses it.

The instructions are written in English — models follow English instructions most reliably — while
the prose a person reads (a pattern's interpretation, the forecast, its advice and warnings) is
generated in Russian, the language of the product's documented example output.

Changing one of these constants means updating ``docs/PROMPTS.md`` in the same commit (AGENTS.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from numenews.models import NewsItem, NumberActivation, Pattern

EXTRACT_RULES = """\
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

EXTRACT_FEW_SHOT = """\
Example

Input:
Text:
The ministry reported 11 new cases on 21 September 2026, and the AI summit was mentioned twice.

Output:
{"numbers": [11, 21, 2026], "symbols": ["AI"]}

Both 21 and 2026 are reported although they only occur inside a date, "AI" is reported because it
occurs in the text, and no number is repeated in the list.
"""

EXTRACT_INSTRUCTIONS = f"{EXTRACT_RULES}\n\n{EXTRACT_FEW_SHOT}"


def build_extract_prompt(text: str, symbols: Sequence[str] = ()) -> str:
    """Return the prompt for one text, with an optional symbol watchlist.

    The watchlist is a caller-owned vocabulary (phase 1.6's ``extract_symbols`` needs one as well),
    so the regex fallback and the model look for the same symbols.
    """
    if not symbols:
        return f"Text:\n{text}"
    watchlist = ", ".join(symbols)
    return f"Watchlist symbols: {watchlist}\n\nText:\n{text}"


PATTERN_RULES = """\
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

PATTERN_FEW_SHOT = """\
Example

Input:
News items to analyse:

1. id: 00000000-0000-0000-0000-000000000001
   date: 2026-09-21 · source: example.com · numerology_value: 11
   title: Eleven ministers resign
   numbers: 11
   text: Eleven ministers resigned today over the budget.

2. id: 00000000-0000-0000-0000-000000000002
   date: 2026-09-21 · source: another.example · numerology_value: 11
   title: Budget vote delayed
   numbers: 11, 21
   text: The budget vote was delayed by eleven votes.

Output:
[{"type": "master", "numbers": [11], "news_ids":
["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"],
"strength": 0.9, "interpretation": "Число 11 повторяется в обеих новостях."}]

Only the two ids from the input are cited, and the connection is reported once, with the stress on
the shared number rather than on the unrelated topics.
"""

PATTERN_INSTRUCTIONS = f"{PATTERN_RULES}\n\n{PATTERN_FEW_SHOT}"

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


FORECAST_RULES = """\
You write the daily numerological reading from facts you are given: the date, its dominant number,
whether a master number (11, 22 or 33) is active, the patterns found in that day's news and the
number activations of the recent past. Take those numbers as given — never compute, reduce or
change one — and do not invent a fact that is not in the input.

Write in Russian:
- "forecast": three to five sentences on what the day holds, grounded in the given number, patterns
  and activations.
- "advice": one or two sentences of practical advice for the day.
- "warnings": one short line per risk the input points at; return an empty list when the day is
  unremarkable.

Name the number, the pattern or the activation each claim rests on, so a reader can check it.
"""

FORECAST_FEW_SHOT = """\
Example

Input:
Date: 2026-09-22
Dominant number: 11 · master number active: yes

Patterns found for this day:
- master · strength 0.90 · numbers 11 · Число 11 повторяется в новостях дня.

Number activations of the recent past:
- 2026-09-21 · 11 · Eleven ministers resigned today over the budget.

Output:
{"forecast": "День проходит под мастер-числом 11: новости дважды вернулись к одиннадцати.",
"advice": "Начинайте разговор с главного и не принимайте решения на эмоциях.",
"warnings": ["Возможен возврат к незавершённому разговору прошлой недели."]}

Every sentence names the number or the activation it rests on, and no new number appears.
"""

FORECAST_INSTRUCTIONS = f"{FORECAST_RULES}\n\n{FORECAST_FEW_SHOT}"

#: How much of one activation's context the forecast prompt shows, in characters.
HISTORY_CONTEXT_LIMIT = 160


def format_history(history: Sequence[NumberActivation]) -> str:
    """Return the recent activations as a prompt block, newest first.

    The order mirrors ``VectorStore.get_history`` (phase 3.7): newest first, and at equal dates by
    ``news_id`` descending, so the same history always renders the same prompt. Contexts are cut to
    :data:`HISTORY_CONTEXT_LIMIT` characters so one long news item cannot crowd the block out.
    """
    if not history:
        return "No number activations were recorded for this window."
    ordered = sorted(
        history,
        key=lambda activation: (activation.date, str(activation.news_id.root)),
        reverse=True,
    )
    return "\n".join(
        f"- {activation.date.isoformat()} · {activation.number} · "
        f"{activation.context[:HISTORY_CONTEXT_LIMIT]}"
        for activation in ordered
    )


def format_patterns(patterns: Sequence[Pattern]) -> str:
    """Return the patterns of the day as a prompt block."""
    if not patterns:
        return "No patterns were found for this day."
    return "\n".join(
        f"- {pattern.type} · strength {pattern.strength:.2f} · "
        f"numbers {', '.join(str(number) for number in pattern.numbers) or 'none'} · "
        f"{pattern.interpretation}"
        for pattern in patterns
    )


def build_forecast_prompt(
    *,
    date: date,
    dominant_number: int,
    master_active: bool,
    patterns: Sequence[Pattern] = (),
    history: Sequence[NumberActivation] = (),
) -> str:
    """Return the prompt for one day: its number, its patterns and the recent activations."""
    return "\n".join(
        (
            f"Date: {date.isoformat()}",
            f"Dominant number: {dominant_number} · master number active: "
            f"{'yes' if master_active else 'no'}",
            "",
            "Patterns found for this day:",
            format_patterns(patterns),
            "",
            "Number activations of the recent past:",
            format_history(history),
        )
    )
