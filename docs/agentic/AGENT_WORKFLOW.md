# Agent workflow

How AI coding agents are expected to work in this repository. It complements
[`AGENTS.md`](../../AGENTS.md) (rules and layout) and [`ROADMAP.md`](../../ROADMAP.md) (what to
build, in what order).

## The loop

1. **Read the roadmap first.** Pick the next unfinished task of the current phase. Do not start a
   phase whose predecessor is still open, and do not invent tasks — a new task goes into its phase
   in `ROADMAP.md`, not into an implicit backlog.
2. **Plan before writing.** For anything larger than a task, write down the goal, the files to
   touch, the verification commands and the risks; get the plan approved before editing.
3. **Implement one task at a time.** A task is one conventional commit
   (`feat(scope): …`, `chore: …`, `test: …`, `docs: …`). If a task grows past its Definition of
   Done, split it in `ROADMAP.md` and commit the smaller piece.
4. **Verify with the real commands**, not by reading code: `make lint`, `make test`, and for
   infrastructure `make dev` + a health check. A task's DoD is a command that must pass, not a
   sentence that says it should.
5. **Tick the roadmap.** Update the task's checkboxes in the same commit, and record a deviation
   next to the task when reality differed from the plan (with the reason).
6. **Record decisions.** An architectural choice needs an ADR from
   [`docs/adr/template.md`](../adr/template.md); a user-visible change updates `CHANGELOG.md`
   under `[Unreleased]`.

## Non-negotiables (from AGENTS.md)

- `numerology/` stays pure: no I/O, no imports from `news`, `vector`, `agents`, `mcp`.
- Pydantic models cross every boundary; no dicts, no free-form LLM JSON, no raw SDK calls.
- Embeddings are local (`fastembed`); no external embedding API, no cloud vector database.
- CLI stdout is JSON only; logs and progress go to stderr through `structlog`.
- No `Any`, no bare `# type: ignore`; `mypy --strict` must pass.
- No CI/CD, Kubernetes, Terraform, LangChain, LlamaIndex or LangGraph.

## Working with the private design brief

`.docs/plan.md` is the author's design brief: useful context, but not the specification. It is
gitignored, and where it disagrees with `AGENTS.md` or `ROADMAP.md`, those win — for example the
package is `numenews` (not `numerology_news`) and the binary is `numenews` (not `nn`).

## Reviewing an agent's work

- Diff against the task's DoD: were the tests written, the docs and ADR updated, the roadmap
  ticked?
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
