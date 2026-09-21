# Numerology

> **Implemented** in `src/numenews/numerology/` (phase 1). The layer is pure: it imports only the
> shared `numenews.models` vocabulary, performs no I/O, and every rule below is enforced by unit
> tests and property-based tests. [ADR 0002](adr/0002-numerology-scope.md) records why the scope is
> exactly this and what it deliberately leaves out.

## Vocabulary

- **Digit sum** — the sum of the decimal digits of a number: `124 → 1 + 2 + 4 = 7`.
- **Reduction** — repeated digit sums until a single digit remains, with the master numbers as the
  only stop.
- **Master number** — `11`, `22` or `33`: not reduced further, they keep their two-digit form.
- **Gematria** — a letter-by-letter sum: Latin `A = 1 … Z = 26`, Cyrillic by alphabet position.
- **Date resonance** — two dates whose reduced values coincide.
- **Activation** — one occurrence of a number in one news item, recorded with date and context.
- **Reading** — the result of `compute_numerology`: the letter sum, the reduced value, and the
  steps between them.

## Reduction

`reduce_number(n)` replaces `n` with its digit sum for as long as the value is greater than `9` and
is not a master number:

| Input | Output | Why |
|---|---|---|
| 19 | 1 | 1+9 = 10 → 1+0 = 1 |
| 11 | 11 | master number, returned unchanged |
| 29 | 11 | 2+9 = 11, which is a master number |
| 38 | 11 | 3+8 = 11, which is a master number |
| 49 | 4 | 4+9 = 13 → 1+3 = 4 |
| 1998 | 9 | 1+9+9+8 = 27 → 9 |
| 999999 | 9 | 6·9 = 54 → 9 |

The domain is the positive integers. `reduce_number(0)` and negative inputs raise `ValueError`
instead of returning a value: `0` is not in the allowed set, and a date always contributes at least
one non-zero digit, so no caller inside the project needs it.

`reduction_steps(n)` renders the same walk for humans and is what `breakdown` uses:

```python
reduction_steps(7)  # ()
reduction_steps(124)  # ("124 -> 1+2+4 = 7",)
reduction_steps(29)  # ("29 -> 2+9 = 11", "11 is a master number and is not reduced further")
reduction_steps(999999)  # ("999999 -> 9+9+9+9+9+9 = 54", "54 -> 5+4 = 9")
```

`reduce_date(d)` sums the digits of the ISO date and reduces that sum. Zero padding never changes a
digit sum, so the result depends on the date, not on how it is written:

| Date | Digits | Output |
|---|---|---|
| 2026-09-21 | 2+0+2+6+0+9+2+1 = 22 | 22 (master) |
| 1998-12-31 | 1+9+9+8+1+2+3+1 = 34 | 7 |
| 0001-01-01 | 0+0+0+1+0+1+0+1 = 3 | 3 |

## Master numbers

```python
MASTER_NUMBERS = frozenset({11, 22, 33})
REDUCED_NUMBERS = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9}) | MASTER_NUMBERS
```

`is_master(n)` answers the single-value question. `check_master_numbers(numbers)` reports on a whole
sequence as `MasterCheckResult(has_master, master_numbers, count)`, where `master_numbers` holds the
**distinct** master numbers in ascending order and `count` counts every **occurrence**:

| Input | `has_master` | `master_numbers` | `count` |
|---|---|---|---|
| `[]` | False | `()` | 0 |
| `[1, 2, 9]` | False | `()` | 0 |
| `[11]` | True | `(11,)` | 1 |
| `[11, 11]` | True | `(11,)` | 2 |
| `[33, 7, 11, 22, 11]` | True | `(11, 22, 33)` | 4 |

An empty sequence is a reading that found no activation, not an error.

## Gematria

`gematria_simple(text)` folds case and sums every letter the value tables know; everything else —
spaces, punctuation, digits, emoji, other scripts — contributes nothing. `gematria_reduce(text)`
reduces that sum with the same master-number stop as `reduce_number`.

**Latin** — `A = 1 … Z = 26`:

| Value | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Letter | A | B | C | D | E | F | G | H | I | J | K | L | M |

| Value | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 | 26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Letter | N | O | P | Q | R | S | T | U | V | W | X | Y | Z |

**Cyrillic** — the 33-letter Russian alphabet by position, `А = 1 … Я = 33`, `Ё` included at `7`
(two tables in a row for width):

| Value | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Letter | А | Б | В | Г | Д | Е | Ё | Ж | З | И |

| Value | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | 25 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Letter | Й | К | Л | М | Н | О | П | Р | С | Т | У | Ф | Х | Ц | Ч |

| Value | 26 | 27 | 28 | 29 | 30 | 31 | 32 | 33 |
|---|---|---|---|---|---|---|---|---|
| Letter | Ш | Щ | Ъ | Ы | Ь | Э | Ю | Я |

Cyrillic letters outside the Russian alphabet (Ukrainian `Ї`, `Ґ`, Serbian `Ђ`, …) are ignored rather
than transliterated or guessed at, and so are Greek, CJK and every other script.

| Input | Sum | Reduced |
|---|---|---|
| `"sun"` | 19 + 21 + 14 = **54** | 9 |
| `"Sun"` | 54 | 9 |
| `"Sun rises"` | 19+21+14+18+9+19+5+19 = **124** | 7 |
| `"k"` | **11** | 11 (master) |
| `"солнце"` | 19+16+13+15+24+6 = **93** | 3 |
| `"sun солнце"` | 54 + 93 = **147** | 3 |
| `""`, `"123!!"`, `"🙂"` | **0** | 0 |

`gematria_reduce` returns `0` for a text without a mapped letter instead of calling `reduce_number`,
whose domain starts at `1`. The sentinel is unambiguous: no positive sum reduces to `0`.

## Date resonance

`date_resonance(d1, d2)` returns the reduced value the two dates share, or `0` when they do not
resonate — again unambiguous, because a reduced date value is never `0`. `find_date_resonances`
reports every unordered pair in input order:

```python
date_resonance(date(2026, 9, 21), date(2026, 9, 12))  # 22
date_resonance(date(2026, 9, 21), date(2026, 9, 22))  # 0

find_date_resonances([date(2026, 9, 21), date(2026, 9, 22), date(2026, 9, 12)])
# [(2026-09-21, 2026-09-12, 22)]
```

Two identical dates resonate by definition, a repeated date forms as many pairs as it has partners,
and fewer than two dates yield `[]`.

## The dominant number of a set

A day's reading needs one number to stand for it, and `dominant_number(values)` decides which from
the reduced values of that day's news: the most frequent value wins, and a tie goes to the larger
value. The result is a `DominantResult` carrying the evidence with the answer — `votes` (how often
the winner occurred) and `considered` (how many values were counted) — so a reader can tell a day
that eleven items agree on from a day that had one item.

```python
dominant_number([11, 11, 11, 7, 3])  # 11, votes 3, considered 5
dominant_number([7, 7, 11, 11])      # 11: the tie goes to the larger value
dominant_number([])                  # 0, votes 0, considered 0
```

`0` is again the sentinel, because no reduced value is ever `0`; a day with no news has no dominant
number, and the pipeline falls back to `reduce_date(day)` — a reading always has a number to rest
on. A value below `1` raises `ValueError`: `compute_numerology` reports a text without letters as
`0`, which means "not computed" and must not vote.

## Regex extraction

The layer never asks a model for anything. These functions are the fallback that keeps the pipeline
running when the extract agent fails (phase 4.2), and they double as the deterministic baseline the
agent's output is compared against.

`extract_numbers_regex(text)` returns every run of ASCII digits as an integer, in text order,
duplicates kept, leading zeros normalised (`"007"` → `7`). Two consequences are deliberate:

- the digits of a date are also numbers: `"published 2026-09-21"` → `[2026, 9, 21]`; a caller that
  wants dates uses `extract_dates_regex` and ignores these;
- a thousands separator is not understood: `"about 1,000 people"` → `[1, 0]`.

`extract_dates_regex(text, *, today=None)` reads three formats, merged by position in the text:

| Format | Example | Result |
|---|---|---|
| ISO | `2026-09-21` | `date(2026, 9, 21)` |
| Dotted | `21.09.2026` | `date(2026, 9, 21)` |
| Russian month, with a year | `15 марта 2026` | `date(2026, 3, 15)` |
| Russian month, without a year | `15 марта` | `date(<year of today>, 3, 15)` |

The genitive form (`15 марта`) and the nominative (`15 Март 2027`) are both accepted,
case-insensitively. A date that does not exist — `31.02.2026`, `2026-13-45` — is skipped instead of
raising, because news text contains typos and one bad date must not lose the others. English month
names are **not** supported in phase 1.6.

`today` is the date whose year completes a year-less match; it defaults to `date.today()`. It is
injectable so that a test — or a caller replaying an old batch — does not depend on the wall clock.
This is the only ambient value the layer ever reads.

`extract_symbols(text, symbols)` returns the requested symbols that occur in `text`, matched
case-insensitively as substrings (so `"AI"` and emoji both work), deduplicated, in the order of the
`symbols` argument. Presence is the primitive here; counting occurrences belongs to the pattern layer,
which compares symbols across news items (phase 5).

## Public API

Everything below is re-exported from `numenews.numerology` and listed in its `__all__`:

| Function | Signature | Notes |
|---|---|---|
| `compute_numerology` | `(text: str) -> NumerologyResult` | The entry point: gematria + reduction + master check |
| `reduce_number` | `(n: int) -> int` | `ValueError` when `n < 1` |
| `reduce_date` | `(d: date) -> int` | Digits of the ISO date |
| `reduction_steps` | `(n: int) -> tuple[str, ...]` | Rendered reduction, used by `breakdown` |
| `is_master` | `(n: int) -> bool` | `11`/`22`/`33` |
| `check_master_numbers` | `(numbers: Sequence[int]) -> MasterCheckResult` | Distinct values and occurrence count |
| `gematria_simple` | `(text: str) -> int` | Unreduced letter sum |
| `gematria_reduce` | `(text: str) -> int` | Reduced sum, `0` when there are no letters |
| `normalize_text` | `(text: str) -> str` | Casefolded, mapped letters only |
| `date_resonance` | `(d1: date, d2: date) -> int` | Shared value, or `0` |
| `find_date_resonances` | `(dates: Sequence[date]) -> list[tuple[date, date, int]]` | Every resonant pair |
| `dominant_number` | `(values: Sequence[int]) -> DominantResult` | Most frequent value, ties to the larger |
| `extract_numbers_regex` | `(text: str) -> list[int]` | All digit runs |
| `extract_dates_regex` | `(text: str, *, today: date \| None = None) -> list[date]` | Three formats |
| `extract_symbols` | `(text: str, symbols: Sequence[str]) -> list[str]` | Present symbols |

Plus the constants `MASTER_NUMBERS` and `REDUCED_NUMBERS`.

`compute_numerology("Sun rises")` returns:

```python
NumerologyResult(
    text="Sun rises",
    gematria=124,
    value=7,
    is_master=False,
    breakdown=("gematria_simple = 124", "124 -> 1+2+4 = 7"),
)
```

The breakdown of a reading always starts with the line `gematria_simple = <sum>`; the reduction
steps follow. A text without a mapped letter has `gematria == value == 0`, `is_master is False` and
the single breakdown line `no letters to sum`. Extraction is not part of `compute_numerology`: a
reading of the text's letters does not depend on what the regexes found, and the two answers stay
separate.

## Invariants

| # | Invariant | Enforced by |
|---|---|---|
| 1 | `reduce_number(n) ∈ REDUCED_NUMBERS` for every `n ≥ 1` | `test_reduction.py`, 1000 hypothesis examples |
| 2 | `reduce_number` is idempotent on its own output | `test_reduction.py` |
| 3 | `reduce_date(d) ∈ REDUCED_NUMBERS` for every date | `test_reduction.py`, `st.dates()` |
| 4 | `gematria_simple(text) ≥ 0` for every text | `test_gematria.py`, `st.text()` |
| 5 | `gematria_reduce(text) ∈ {0} ∪ REDUCED_NUMBERS` for every text | `test_gematria.py`, `st.text()` |
| 6 | `date_resonance` is symmetric and never a value outside `{0} ∪ REDUCED_NUMBERS` | `test_resonance.py`, a whole month |
| 7 | `numenews.numerology` imports none of `news`, `vector`, `agents`, `mcp`, `cli` | `test_numerology_api.py`, a fresh interpreter |

Property tests use hypothesis; the table cases in the same files pin the concrete values quoted
above. Coverage of `src/numenews/numerology/` is 100% (statements and branches).

## Sentinel values

| Sentinel | Meaning | Where |
|---|---|---|
| `0` | the text has no mapped letter (`gematria`, `value` of `NumerologyResult`) | gematria layer |
| `0` | the two dates do not resonate | `date_resonance` |
| `None` | the news item's `numerology_value` was not computed yet | `NewsItem` (phase 4 fills it) |

`0` is never a reduced value, so both zero sentinels are unambiguous; `reduce_number` rejects it
rather than returning it.

## Layering

`numerology` imports `numenews.models` and nothing else from the project. `models` imports nothing
from `numenews`, so the dependency is acyclic and the pure layer can be tested without Qdrant,
without an LLM and without a network. ADR 0002 records this and the correction it implies for the
layer table in [ARCHITECTURE.md](ARCHITECTURE.md).

## Out of scope

The following are intentionally **not** implemented, and adding one is a new decision for an ADR:

- Chaldean and Kabbalah gematria variants, the 9-cycle Russian letter table, and any transliteration
  of Cyrillic onto Latin values — the project keeps one table per script;
- astrology, tarot or any reading that is not arithmetic on numbers, dates and letters;
- English month names in `extract_dates_regex`;
- interpreting a reading (what `7` "means") — that is the forecast agent's job (phase 4.4);
- extracting numbers as part of `compute_numerology`.
