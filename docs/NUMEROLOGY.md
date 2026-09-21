# Numerology

> **Phase 0 template.** Phase 1 implements these rules in `src/numenews/numerology/` and completes
> this document with the worked examples (ROADMAP.md 1.8). Definitions below are the ones the
> roadmap commits to; anything still marked *open* is decided in phase 1.

## Vocabulary

- **Digit sum** — the sum of the decimal digits of a number.
- **Reduction** — repeated digit sum until a single digit remains.
- **Master number** — 11, 22 or 33: reduced no further, they keep their two-digit form.
- **Gematria** — a letter-by-letter sum, Latin `A=1 … Z=26`, with the Cyrillic alphabet mapped in
  phase 1.4 (*open*: the Cyrillic offset).
- **Date resonance** — two dates whose reduced values coincide.
- **Activation** — one occurrence of a number in one news item, recorded with date and context.

## Reduction

`reduce_number(n)` reduces `n` to `1–9`, except that `11`, `22` and `33` are returned unchanged
(master numbers). `reduce_date(d)` reduces the digit sum of the ISO date; `0` cannot occur because
a non-zero number is required as input.

| Input | Output | Why |
|---|---|---|
| 19 | 1 | 1+9 = 10 → 1+0 = 1 |
| 11 | 11 | master number |
| 29 | 11 | 2+9 = 11, which is a master number |
| 1998 | 9 | 1+9+9+8 = 27 → 9 |

## Master numbers

`MASTER_NUMBERS = frozenset({11, 22, 33})`. `check_master_numbers` reports whether a sequence
contains one, which ones, and how many — duplicates count once in the set and once per occurrence
(*open*: the exact pair of fields in `MasterCheckResult`, phase 1.3).

## Gematria

`gematria_simple` sums letters case-insensitively and ignores whitespace and punctuation;
`gematria_reduce` applies `reduce_number` to that sum. Worked example: `"sun"` → 19 + 21 + 14 = 54.

## Date resonance

`date_resonance(d1, d2)` compares reduced values; `find_date_resonances(dates)` returns the
matching pairs. Same-date pairs are reported as resonant by definition.

## Invariants (property-tested in phase 1)

1. `reduce_number(n)` ∈ {1…9, 11, 22, 33} for every `n`.
2. `reduce_number` is idempotent on its own output.
3. `gematria_simple(text)` ≥ 0 for every text.
4. `gematria_reduce(text)` ∈ {1…9, 11, 22, 33} for every non-empty text.
