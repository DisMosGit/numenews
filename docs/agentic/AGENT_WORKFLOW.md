# Agent workflow

How AI coding agents are expected to work in this repository. It complements
[`AGENTS.md`](../../AGENTS.md) (rules and layout) and the OpenSpec change in flight (what to
build, in what order).

## The loop

1. **Read the change first.** `openspec list` shows what is in flight; read its `proposal.md`,
   `design.md` and `tasks.md` before touching anything. Work on the next unticked `tasks.md` item.
   Do not invent work outside a change — a new task goes into the change's `tasks.md`, and a new
   idea becomes a change of its own (`/openspec-propose`) or a GitHub issue.
2. **Plan before writing.** For anything larger than a task, write down the goal, the files to
   touch, the verification commands and the risks; get the plan approved before editing.
3. **Implement one task at a time.** A `tasks.md` item is one conventional commit
   (`feat(scope): …`, `chore: …`, `test: …`, `docs: …`). If an item grows past what its spec delta
   describes, stop and update the change's artifacts instead of widening it silently.
4. **Verify with the real commands**, not by reading code: `make lint`, `make test`, and for
   infrastructure `make dev` + a health check. A task's verification is a command that must pass,
   not a sentence that says it should.
5. **Tick the task.** Update its checkbox in `tasks.md` in the same commit, and record a deviation
   next to it when reality differed from the plan (with the reason).
6. **Record decisions.** An architectural choice needs an ADR from
   [`docs/adr/template.md`](../adr/template.md); a user-visible change updates `CHANGELOG.md`
   under `[Unreleased]`.
7. **Archive the change** once every box is ticked and `openspec validate "<name>" --strict` passes:
   `openspec archive "<name>"` merges the spec deltas into `openspec/specs/`, which is what makes
   the new behaviour the documented baseline.

## Non-negotiables (from AGENTS.md)

- `numerology/` stays pure: no I/O, no imports from `news`, `vector`, `agents`, `mcp`.
- Pydantic models cross every boundary; no dicts, no free-form LLM JSON, no raw SDK calls.
- Embeddings are local (`fastembed`); no external embedding API, no cloud vector database.
- CLI stdout is JSON only; logs and progress go to stderr through `structlog`.
- No `Any`, no bare `# type: ignore`; `mypy --strict` must pass.
- No CI/CD, Kubernetes, Terraform, LangChain, LlamaIndex or LangGraph.

## Working with the private design brief

`.docs/plan.md` is the author's design brief: useful context, but not the specification. It is
gitignored, and where it disagrees with `AGENTS.md` or `openspec/specs/`, those win — for example
the package is `numenews` (not `numerology_news`) and the binary is `numenews` (not `nn`).

## Reviewing an agent's work

- Diff against the task's verification: were the tests written, the docs and ADR updated, the
  `tasks.md` box ticked?
- If the work changed behaviour the specs describe, was the change's spec delta updated — and does
  the change still validate?
- Re-run the verification commands yourself; do not trust a summary that claims they passed.
- Check the failure paths: an LLM or news API being down, an empty collection, a duplicate ingest —
  graceful degradation is part of the design, not a nice-to-have.

## See also

- [`CONVENTIONS.md`](CONVENTIONS.md) — the code conventions this workflow assumes.
- [`GUARDRAILS.md`](GUARDRAILS.md) — what an agent must not do, and what to do instead.
- [`PROMPTING_PLAYBOOK.md`](PROMPTING_PLAYBOOK.md) — reusable prompts for planning, implementing,
  reviewing, writing an ADR and diagnosing a failing check.
- [`EVAL_OF_AGENT.md`](EVAL_OF_AGENT.md) — how agent-generated work is reviewed, with a checklist.
- [`TOOLING.md`](TOOLING.md) — the tool surface, the Makefile targets and the two environments.
