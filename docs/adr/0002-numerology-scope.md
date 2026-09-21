# 2. Numerology scope: reduction, master numbers, gematria, date resonance, regex extraction

## Status

Accepted (phase 1)

## Date

2026-09-21

## Context

The domain of this project is numerology, and "numerology" is not one system: Pythagorean reduction,
Chaldean letter values, Kabbalah gematria, the 9-cycle Russian letter tables, and astrology-adjacent
readings all travel under the name. Each answers a different question and produces different numbers
for the same input. A project that mixes them silently produces results nobody can check, and a
reading that cannot be checked is not a feature — it is decoration.

Three further constraints shape the layer:

- **The layer is the project's foundation.** Phases 4, 5, 6 and 7 build agents, a pipeline, MCP tools
  and a CLI on top of it. Whatever it cannot answer, the layers above must not invent; whatever it
  answers ambiguously, they inherit as a bug.
- **It must be testable without infrastructure.** AGENTS.md requires it to be pure — no I/O, and no
  imports from `news`, `vector`, `agents` or `mcp` — so that its invariants can be property-tested
  without Qdrant, without an LLM and without a network.
- **The numbers must not come from a model.** Local computation is the source of truth; a model may
  later interpret a number, but it must not be the thing that computes it, or the pipeline becomes
  unverifiable and non-reproducible.

`ROADMAP.md` 1.1 additionally places the result models (`NumerologyResult`, `MasterCheckResult`) in
`src/numenews/models/`, while the phase-0 layer table in `docs/ARCHITECTURE.md` describes `numerology`
as importing "nothing". Those two cannot both hold as written.

The phase-0 draft of `docs/NUMEROLOGY.md` left two rules open: the Cyrillic offset in gematria, and
the exact fields of `MasterCheckResult`. Both are settled here.

## Decision

We will implement exactly five numeric rules in `src/numenews/numerology/`, and no others:

1. **Reduction with a master stop.** `reduce_number(n)` repeatedly replaces `n` with its digit sum
   while the value is greater than 9 and is not a master number. The domain is the positive integers;
   zero and negatives raise `ValueError` rather than returning an invented value.
2. **Master numbers `11`, `22`, `33`.** They stop the reduction and are reported as themselves.
   `check_master_numbers` distinguishes distinct values (`master_numbers`, ascending) from occurrences
   (`count`), so `[11, 11]` is one distinct master number seen twice.
3. **Gematria with one table per script.** Latin is `A = 1 … Z = 26`. Cyrillic is the 33-letter
   Russian alphabet by position, `А = 1 … Я = 33` with `Ё = 7`; letters outside that alphabet and
   every other script are ignored, not transliterated. Normalisation folds case and drops everything
   that is not a mapped letter, so a reading depends only on letters.
4. **Date resonance.** Two dates resonate when `reduce_date` gives the same value; `date_resonance`
   returns that shared value or `0`, and `find_date_resonances` returns every unordered pair in input
   order.
5. **Regex extraction as the LLM-free fallback.** `extract_numbers_regex`, `extract_dates_regex`
   (ISO, `DD.MM.YYYY`, Russian month names) and `extract_symbols` extract without a model, so the
   pipeline still works when the extract agent of phase 4.2 fails.

We will put the result models in `numenews.models` and let `numerology` import them; `models` imports
nothing from `numenews`. `docs/ARCHITECTURE.md`'s row for `numerology` therefore reads `models`, not
"nothing". The full package docstrings, examples and invariants live in
[`docs/NUMEROLOGY.md`](../NUMEROLOGY.md).

We will represent "nothing to report" with explicit sentinels instead of exceptions or magic values:
`0` for a text without a mapped letter and for a non-resonant pair (no reduced value is ever `0`), and
`None` for a news item whose `numerology_value` has not been computed yet.

`compute_numerology(text)` will read the *letters* of a text; finding numbers and dates in it stays
with the extraction functions and the agent, because those are different questions.

## Consequences

- **What becomes easier.** Every rule is a pure function of its arguments, so the invariants are
  property-testable and the layer reaches 100% statement and branch coverage. The layers above can
  treat a reading as data: `NumerologyResult` and `MasterCheckResult` are frozen, strict Pydantic
  models, which an MCP tool can return unchanged (phase 6.4) and the CLI can print as JSON (phase 7).
- **What becomes harder.** Adding a rule now costs an ADR, because the scope is closed on purpose. A
  reader who wants Chaldean values, a 9-cycle Cyrillic table or English month names will not find
  them, and the answer is not "the function accidentally handles it" but "this ADR says why not".
- **What it rules out.** No model, no network, no Qdrant and no clock inside the layer. The one
  ambient value — the current year for a year-less date — is injectable
  (`extract_dates_regex(..., today=...)`), so a test and a replay of an old batch stay deterministic.
  `reduce_number(0)` raising is permanent: loosening it would weaken invariant 1 for every caller.
- **What it constrains later.** Phase 4.2 must fall back to `extract_*_regex` rather than inventing
  its own parsing; phase 5 must not compute numbers in the pipeline; the `Pattern.type` vocabulary in
  `numenews.models` is the one place the *kinds* of pattern are named, and adding a member there is
  additive. Extraction results and readings stay separate in the JSON the CLI prints.
- **Follow-up work.** Phase 10.3 still owes ADR 0008 (`fastembed` vs OpenAI) and 0009 (`hishel`); this
  ADR supersedes nothing and is not superseded.

## References

- [`ROADMAP.md`](../../ROADMAP.md) phase 1 (tasks 1.1–1.8)
- [`docs/NUMEROLOGY.md`](../NUMEROLOGY.md) — the rules, worked examples and invariants
- [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) — the layer table this ADR corrects one row of
- [`AGENTS.md`](../../AGENTS.md) — the purity rule and the boundary contracts
- [ADR 0001](0001-record-architecture-decisions.md) — how decisions are recorded
