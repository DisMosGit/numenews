"""Unit tests for the activation bookkeeping of the ingest step (ROADMAP 5.2).

Both functions are pure: a news item and its numbers go in, activations come out. That makes the
two rules of the ingest step testable without Qdrant — one activation per ``(news_id, number)``
pair, and a context that is always a readable, non-empty snippet — while the storage itself is
covered by the integration tests.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from numenews.models import NewsId, NewsItem
from numenews.pipeline.steps import CONTEXT_LIMIT, activate, context_snippet, reading_text

ITEM_ID = UUID("00000000-0000-0000-0000-000000000001")


def _item(
    *,
    title: str = "Eleven ministers resign",
    text: str = "Eleven ministers resigned today over the budget.",
    numbers: tuple[int, ...] = (),
) -> NewsItem:
    """Return one news item with a known id, so an activation can cite it."""
    return NewsItem(
        id=NewsId(ITEM_ID),
        title=title,
        text=text,
        source="example.com",
        date=date(2026, 9, 21),
        url="https://example.com/a",
        numbers=numbers,
    )


def test_the_context_is_the_sentence_around_the_number() -> None:
    """The snippet says what the digits mean, which is the whole point of storing it."""
    text = "Markets fell. The 11th hour deal failed late on Tuesday."

    assert context_snippet(text, 11) == "The 11th hour deal failed late on Tuesday."


def test_the_context_starts_at_the_sentence_that_opens_the_number() -> None:
    """A sentence boundary keeps the snippet from starting mid-word."""
    text = "A long preamble about nothing at all. The 7th vote failed."

    assert context_snippet(text, 7) == "The 7th vote failed."


def test_a_number_absent_from_the_text_falls_back_to_the_opening() -> None:
    """The model may read "eleven" where the regex read nothing; the context stays meaningful."""
    text = "Eleven ministers resigned over the budget."

    assert context_snippet(text, 11) == text


def test_a_blank_text_still_yields_a_non_empty_context() -> None:
    """`numbers` embeds the context, so an empty one would collapse every activation to a point."""
    assert context_snippet("   ", 11) == "11"


def test_the_context_is_cut_to_the_limit() -> None:
    """One long article must not crowd the history window out."""
    text = f"The 11 said. {'x' * (CONTEXT_LIMIT * 2)}"

    snippet = context_snippet(text, 11)

    assert len(snippet) == CONTEXT_LIMIT
    assert snippet.startswith("The 11 said.")


def test_the_context_collapses_whitespace() -> None:
    """A feed's embedded newlines would otherwise reach the prompt as ragged lines."""
    assert context_snippet("The  11th\n\nhour deal", 11) == "The 11th hour deal"


def test_activate_makes_one_activation_per_number() -> None:
    """One pair per `(news_id, number)`: the point id of the `numbers` collection."""
    item = _item(numbers=(11, 2026))

    activations = activate(item, item.numbers)

    assert [activation.number for activation in activations] == [11, 2026]
    assert {activation.date for activation in activations} == {date(2026, 9, 21)}
    assert {activation.news_id for activation in activations} == {NewsId(ITEM_ID)}
    assert all(activation.context for activation in activations)


def test_activate_drops_a_repeated_number() -> None:
    """`ExtractedNumbers.numbers` is already unique, but the writer does not rely on that."""
    item = _item(numbers=(11, 11))

    assert len(activate(item, (11, 11))) == 1


def test_activate_without_numbers_makes_nothing() -> None:
    """An article that states no number contributes no memory."""
    assert activate(_item(), ()) == []


def test_reading_text_joins_the_headline_and_the_body() -> None:
    """The value of an item is read from both, and the blank line keeps the two apart."""
    assert reading_text(_item(title="Headline", text="Body")) == "Headline\n\nBody"


def test_reading_text_never_leaves_a_blank_string() -> None:
    """A `f"{...}\\n\\n{...}".strip()` of two blanks is empty; the URL is the caller's fallback."""
    assert reading_text(_item(title="", text="")) == ""
