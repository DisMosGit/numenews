"""Gematria: turning letters into a number.

Latin runs ``A=1 … Z=26``. Cyrillic follows the 33-letter Russian alphabet by position,
``А=1 … Я=33`` with ``Ё=7`` (ADR 0002 records the choice); other Cyrillic letters — ``Ї``, ``Ґ``,
``Ђ`` — and every other script are ignored rather than guessed at.

Normalisation is deliberately lossy and one-way: case is folded, and everything that is not a mapped
letter (spaces, punctuation, digits, emoji) drops out. A reading therefore depends only on the
letters, and a text without a single one has the sum ``0``. ``gematria_reduce`` returns that ``0``
unchanged instead of calling :func:`~numenews.numerology.reduction.reduce_number`, whose domain
starts at ``1``; the sentinel is unambiguous because no positive sum reduces to ``0``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from numenews.numerology.reduction import reduce_number

# The Russian alphabet in its canonical order: 33 letters, Ё between Е and Ж.
_CYRILLIC_ALPHABET = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

LATIN_VALUES: Mapping[str, int] = MappingProxyType(
    {chr(ord("a") + offset): offset + 1 for offset in range(26)}
)
# A=1 … Z=26, lowercase keys only: normalisation folds case before the lookup.
CYRILLIC_VALUES: Mapping[str, int] = MappingProxyType(
    {letter: position for position, letter in enumerate(_CYRILLIC_ALPHABET, start=1)}
)
# А=1 … Я=33, lowercase keys only, Ё included at its alphabet position.

_LETTER_VALUES: Mapping[str, int] = MappingProxyType({**LATIN_VALUES, **CYRILLIC_VALUES})


def normalize_text(text: str) -> str:
    """Fold case and keep only the letters the value tables know.

    Args:
        text: Any text; digits, punctuation, emoji and unmapped scripts are dropped.

    Returns:
        The mapped letters, casefolded and in their original order.
    """
    return "".join(character for character in text.casefold() if character in _LETTER_VALUES)


def gematria_simple(text: str) -> int:
    """Sum the mapped letters of ``text`` without reducing.

    Args:
        text: The text to sum.

    Returns:
        The letter sum, or ``0`` when the text has no mapped letter.

    Examples:
        ``gematria_simple("sun")`` is ``19 + 21 + 14 = 54``.
    """
    return sum(_LETTER_VALUES[character] for character in normalize_text(text))


def gematria_reduce(text: str) -> int:
    """Reduce the letter sum of ``text``.

    Args:
        text: The text to reduce.

    Returns:
        The reduced sum, a member of
        :data:`~numenews.numerology.constants.REDUCED_NUMBERS`, or ``0`` when the text has no
        mapped letter.

    Examples:
        ``gematria_reduce("sun")`` is ``54 -> 9``; ``gematria_reduce("k")`` is ``11``, a master
        number.
    """
    total = gematria_simple(text)

    return reduce_number(total) if total > 0 else 0
