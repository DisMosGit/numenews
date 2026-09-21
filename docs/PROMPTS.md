# Prompts

Every prompt numenews sends lives in `src/numenews/agents/prompts.py`. Nothing in the agents builds
prompt text inline, so this document and that module are the two places a prompt can be read — and
AGENTS.md requires both to change together.

Each agent has three pieces:

| Piece | What it is | Used by |
|---|---|---|
| `*_RULES` | the instruction block: the task, the allowed values and the prohibitions | composed into `*_INSTRUCTIONS` |
| `*_FEW_SHOT` | one worked example, input and answer | composed into `*_INSTRUCTIONS` |
| `*_INSTRUCTIONS` | `f"{rules}\n\n{few_shot}"` — what an `Agent` is constructed with | the agent's `instructions` |
| `build_*_prompt(...)` | the facts of one call, rendered | `Agent.run(...)` |

Rules and facts are separate on purpose: the rules are constant and snapshot-tested, while the facts
change per call. `tests/unit/test_agents_prompts.py` compares each rendered prompt with the exact
text written there — the project has no snapshot library, so the literal is the snapshot.

## Talking to the model

`build_llm_model()` (`agents/llm.py`) returns an `OpenAIChatModel` over an `OpenAIProvider`. The
*chat completions* API is deliberate; the bare `"openai:"` model string would select the newer
Responses API, which third-party compatible servers do not implement. Endpoints come from settings
(`.env.example`):

| Endpoint | `OPENAI_BASE_URL` | `OPENAI_API_KEY` |
|---|---|---|
| OpenAI | *(blank — the default)* | required |
| OpenRouter | `https://openrouter.ai/api/v1` | required |
| Ollama / vLLM / LM Studio | `http://localhost:11434/v1` | ignored, a placeholder is sent |

`LLM_MODEL` names the model at that endpoint (`gpt-4o-mini`, `openai/gpt-4o-mini`,
`llama3.2`, …). No key and no base URL is a configuration error — `build_llm_model()` raises
`LLMConfigurationError` before the first request instead of failing mid-run. The reasoning behind the
provider choice is in [ADR 0004](adr/0004-pydantic-ai-choice.md).

## The model writes a draft, never a domain model

Each agent declares a `pydantic_ai` `output_type` from `agents/schemas.py` — `ExtractionDraft`,
`list[PatternDraft]`, `ForecastDraft` — and the agent turns it into `ExtractedNumbers`,
`list[Pattern]` or `Forecast`. The draft holds only what a model can honestly know; everything else
is computed by the layers that own it:

| Domain field | Whose it is |
|---|---|
| `ExtractedNumbers.sources` | ours: provenance of the extraction (`llm`, `regex`) |
| `Pattern.id`, `Pattern.discovered_at` | ours: the id is a `uuid5` of the pattern's content, the timestamp belongs to `save_pattern` (3.5) |
| `Pattern.news_ids` | the input: ids the model may copy but not invent; unknown ones are dropped |
| `Forecast.date`, `dominant_number`, `master_active` | `numenews.numerology`, through the pipeline (AGENTS.md keeps numerology out of the agents) |
| `Forecast.patterns` | phase 4.3 or Qdrant |
| `Pattern.interpretation`, `Forecast.forecast` / `advice` / `warnings` | the model |

Draft fields are shaped like JSON — arrays and strings rather than tuples and `RootModel[UUID]`
wrappers — because `pydantic-ai` validates tool arguments in Python mode, where a strict `tuple`
refuses a list and a strict `UUID` refuses a string. The drafts keep `strict=True`; identity strings
are parsed when the domain object is assembled.

## Language

The instructions and the worked examples' inputs are English: models follow English instructions
most reliably. The prose a person reads — `Pattern.interpretation` and
`Forecast.forecast`/`advice`/`warnings` — is generated **in Russian**, which is what the README's
example output shows. Every prose-producing rule block says so explicitly.

## Extract numbers

`EXTRACT_RULES` + `EXTRACT_FEW_SHOT` → `EXTRACT_INSTRUCTIONS`; facts through
`build_extract_prompt(text, symbols)`. Output: `ExtractionDraft`.

Why the rules read the way they do:

- **Dates count as numbers.** `extract_numbers_regex` is format-agnostic (phase 1.6) and returns the
  components of a date, so the model is asked for the same reading rather than for "interesting"
  numbers only.
- **No arithmetic.** Reduction, master numbers and gematria belong to `numerology/` (AGENTS.md); the
  prompt forbids computing anything, and the layer keeps the guarantee testable.
- **A watchlist, not a vocabulary.** Symbols come from the text plus a caller-supplied list. The
  vocabulary is the caller's because `extract_symbols` needs one too (phase 1.6), and both the model
  and the fallback must look for the same symbols.
- **The regex pass always runs.** The model's reading is merged with `extract_numbers_regex` (model
  first, duplicates dropped); a failed run falls back to the regex reading alone, and
  `ExtractedNumbers.sources` records which strategies contributed (ROADMAP 4.2).

```
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
```

```
Example

Input:
Text:
The ministry reported 11 new cases on 21 September 2026, and the AI summit was mentioned twice.

Output:
{"numbers": [11, 21, 2026], "symbols": ["AI"]}

Both 21 and 2026 are reported although they only occur inside a date, "AI" is reported because it
occurs in the text, and no number is repeated in the list.
```

The prompt itself is the text, prefixed with the watchlist when there is one:

```
Watchlist symbols: AI, $

Text:
<the news text>
```

## Find patterns

`PATTERN_RULES` + `PATTERN_FEW_SHOT` → `PATTERN_INSTRUCTIONS`; facts through
`build_pattern_prompt(news)`. Output: `list[PatternDraft]`.

Each item is rendered with the id the model must cite, its date, source, the numbers extracted
earlier, its reduced value and its text (first `PATTERN_TEXT_LIMIT = 1000` characters, so one long
article cannot crowd the others out):

```
News items to analyse:

1. id: 00000000-0000-0000-0000-000000000001
   date: 2026-09-21 · source: example.com · numerology_value: 11
   title: Eleven ministers resign
   numbers: 11, 21
   text: Eleven ministers resigned today.
```

The connection kinds are the closed `PatternType` literal of phase 1.1 (`repetition`, `master`,
`resonance`, `symbol`, `hidden`), so the model cannot invent a kind the schema rejects. The rules
also bound `strength` to `[0, 1]` (enforced by Pydantic, ROADMAP 4.3) and demand Russian
`interpretation`.

```
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
```

```
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
```

An empty news list never reaches the model: there is nothing to connect, so `find_patterns` returns
`[]` without a request.

## Build the forecast

`FORECAST_RULES` + `FORECAST_FEW_SHOT` → `FORECAST_INSTRUCTIONS`; facts through
`build_forecast_prompt(date=…, dominant_number=…, master_active=…, patterns=…, history=…)`.
Output: `ForecastDraft`.

```
Date: 2026-09-22
Dominant number: 11 · master number active: yes

Patterns found for this day:
- master · strength 0.90 · numbers 11 · Число 11 повторяется в новостях дня.

Number activations of the recent past:
- 2026-09-21 · 11 · Eleven ministers resigned today over the budget.
```

- The day's number and its master status are **given**; the model is forbidden from computing,
  reducing or changing a number, so no numerology runs in the agent.
- `patterns` are rendered one per line with their type, strength and interpretation;
  `format_patterns([])` writes `No patterns were found for this day.`
- `history` renders as `- <date> · <number> · <context>` (one line per activation, contexts cut to
  `HISTORY_CONTEXT_LIMIT = 160` characters), newest first and at equal dates by `news_id`
  descending — the order of `VectorStore.get_history` (phase 3.7), so the same history always
  produces the same prompt. `format_history([])` writes
  `No number activations were recorded for this window.` Phase 8.3 feeds the real 30-day window in.
- `forecast` and `advice` may not be blank: `ForecastDraft` rejects an empty string, so a reading
  that says nothing is a failed run to retry, not a result.

```
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
```

```
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
```

## Changing a prompt

1. Edit the constant or builder in `src/numenews/agents/prompts.py`.
2. Update the matching section here — AGENTS.md requires the doc to change in the same commit.
3. Update the literal in `tests/unit/test_agents_prompts.py`. A few-shot example is parsed and
   validated against its draft schema there, so an example the model could not legally answer fails
   the suite.
4. Run `make lint && make test`.

## Tests

| Test | Guards |
|---|---|
| `tests/unit/test_agents_prompts.py` | the exact rendering of every prompt, the rules + few-shot composition, that the examples validate, and that each agent sends its instructions |
| `tests/unit/test_agents_extract.py` | merging, the regex fallback and `sources` |
| `tests/unit/test_agents_pattern.py` | unknown ids dropped, deterministic ids, out-of-range `strength` rejected |
| `tests/unit/test_agents_forecast.py` | every `Forecast` field, history rendering and blank prose rejected |

No test reaches a real endpoint: `tests/conftest.py` sets `pydantic_ai.models.ALLOW_MODEL_REQUESTS =
False`, and every agent receives a `TestModel`/`FunctionModel` written in
`tests/unit/agent_fakes.py`.
