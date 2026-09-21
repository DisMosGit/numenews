# 4. pydantic-ai as the agent runtime, and the draft boundary

## Status

Accepted (phase 4)

## Date

2026-09-21

## Context

Phase 4 adds the three reasoning steps of the pipeline: reading numbers and symbols out of a news
text, connecting news items, and writing the day's reading. Four questions had to be answered
together, because each constrains the others.

**Which runtime?** `AGENTS.md` rules out LangChain, LlamaIndex and LangGraph, and names
`pydantic-ai` as the orchestrator, so the real question is which shape of it: the `pydantic-ai`
meta-package, which hard-depends on the `anthropic`, `google`, `logfire`, `evals`, `mcp` and `web`
extras, or `pydantic-ai-slim` with only the extra the project uses.

**Which protocol?** The project promises "any OpenAI-compatible endpoint" (ROADMAP 4.1) —
OpenRouter, a local Ollama, vLLM — and those servers implement the *chat completions* API.
`pydantic-ai` resolves the bare `"openai:"` model string to the newer Responses API, which they do
not implement.

**What does the model get to decide?** A `pydantic_ai.Agent` validates its output against a Pydantic
model, and the roadmap's first sketch (4.2–4.4) passed the domain models straight to `output_type`.
But those models carry fields the model cannot honestly know: `ExtractedNumbers.sources` is
provenance, `Pattern.id` is identity that phase 3.5 stores as a Qdrant point id,
`Pattern.discovered_at` belongs to `save_pattern`, and `Forecast.date`, `dominant_number`,
`master_active` and `patterns` are decided by `numerology/` and by storage. Asking for them invites
invention, and a wrong UUID in a strict `RootModel[UUID]` rejects the whole answer.

A second, mechanical problem sits underneath: `pydantic-ai` validates tool arguments in Python mode,
where a strict `tuple` refuses a list and a strict `UUID` refuses a string, so a domain model with
`strict=True` and tuple fields rejects every well-formed JSON answer a model can produce.

**How is any of this tested?** `AGENTS.md` promises a demo path with no API keys, the repository
holds no `.env`, and an LLM call in a test would be slow, non-deterministic and expensive.

## Decision

We will use **`pydantic-ai-slim[openai]` 2.x** as the only agent runtime, and give it a boundary of
its own.

- `agents/llm.py::build_llm_model()` returns an **`OpenAIChatModel` over an `OpenAIProvider`** built
  from `Settings` (`llm_model`, `openai_base_url`, `openai_api_key`). Chat completions, not the
  Responses API, so OpenRouter and local servers work. A keyless base URL gets a placeholder key; no
  key and no base URL raises `LLMConfigurationError` before the first request.
- The model's `output_type` is a **draft** from `agents/schemas.py` — `ExtractionDraft`,
  `list[PatternDraft]`, `ForecastDraft` — and the agent assembles the domain model:
  provenance, a deterministic `PatternId` (`uuid5` over type, numbers and cited ids, the idiom of
  `news.items.news_id`), and the numerological fields the caller supplies. `ExtractionDraft` and
  `ForecastDraft` fill exactly what the model saw; `PatternDraft.news_ids` are parsed and filtered
  against the items that were actually passed.
- Drafts stay `strict=True` but are shaped like JSON (arrays, strings) for the validation-mode reason
  above; identity strings are parsed by the agent.
- Each agent is a small class that **composes** an `Agent` (not a subclass) and exposes one typed
  async method: `extract`, `find_patterns`, `forecast`. The model is injectable
  (`model: Model | None`), which is how the tests run.
- Extract keeps a deterministic fallback: the regex pass of phase 1.6 always runs, and a failed
  model run (any `AgentRunError`) degrades to `extract_numbers_regex` with
  `ExtractedNumbers.sources == ("regex",)`. Pattern and forecast raise `AgentExecutionError`
  instead — phase 5 decides how to degrade, and an empty list must not be confused with "nothing
  connects".
- Prompts live in `agents/prompts.py` as `*_RULES` + `*_FEW_SHOT` → `*_INSTRUCTIONS`, are documented
  verbatim in `docs/PROMPTS.md`, and are snapshot-tested with literal expected strings.
- Instructions are English and generated prose is Russian, matching the README's example output.
- Tests never reach a network: they hand each agent a `TestModel` or `FunctionModel`
  (`tests/unit/agent_fakes.py`) and `tests/conftest.py` sets
  `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False`, so an accidental real request fails loudly.

## Consequences

Easier: every agent output is a validated domain model, so phase 5 composes the steps without
parsing anything; the MCP tools of phase 6 and the CLI of phase 7 can reuse the same three classes;
the endpoint is configuration, not code; and the whole suite stays offline and fast (100 % coverage
of `agents/`).

Harder and worth remembering:

- The dependency is not free: `pydantic-ai-slim[openai]` brings `openai`, `httpx2`, `tiktoken`,
  `pydantic-graph`, `genai-prices` and `logfire-api` into the runtime environment.
- Two schemas now describe one answer (draft and domain model). That is the price of keeping
  identity and numerology out of the model's hands; a field belongs in a draft only if the model can
  know it.
- `OpenAIProvider` selects a model profile using OpenAI model names even with a custom `base_url`, so
  a gateway serving a non-OpenAI model may lose provider-specific capabilities. Nothing in phases 4–8
  depends on those capabilities.
- No live LLM run is possible in this repository (no key, no `.env`), so phase 4 — like phase 2 with
  `respx` — closes on test doubles. The endpoint construction itself is still tested for real.
- A prompt change is a three-file change: `prompts.py`, `docs/PROMPTS.md`, and the literals in
  `tests/unit/test_agents_prompts.py`.

## References

- `ROADMAP.md` phases 4.1–4.6 and 8.3
- `docs/PROMPTS.md` — every prompt, verbatim, with its rationale
- [ADR 0002](0002-numerology-scope.md) — numerology is pure logic; the agents never compute a number
- [ADR 0003](0003-local-embeddings.md) — the layer rules and the `uuid5` identity idiom
- `pydantic-ai` documentation: <https://pydantic.dev/docs/ai/>
