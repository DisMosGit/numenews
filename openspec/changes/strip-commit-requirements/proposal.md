# Proposal

## Why

Nine documents make committing a *requirement of doing the work*. `AGENTS.md` pins "one atomic commit
per `tasks.md` item, with its checkbox ticked in the same commit"; `CONTRIBUTING.md` repeats it as
workflow step 3; six `docs/agentic/` documents, `README.md` and `docs/PROMPTS.md` restate it; and
`GUARDRAILS.md` carries it into five separate rules, two of which are not commit rules at all
(`Do not commit .env or .cache/`, and the docs that must accompany the work).

That coupling is wrong in both directions.

It is wrong for an agent that is not committing. The sentences say a task is not done until its
checkbox, its docs and its ADR land *in one commit* — but the repository's own commit skill ends with
"never commit unless committing is what was asked for". The result is work that ticks a box described
in terms of a commit that never happens, and edits deferred waiting for a "same commit" moment that
does not arrive. Atomicity is a property of a **task**, not of a commit, and the documentation should
say what it means.

It is wrong for the log. Because the docs route the *reason* into the commit message
(`GUARDRAILS.md`: "the reason in the commit message", `EVAL_OF_AGENT.md`), while the commit skill only
asks for a body "when the *why* is non-obvious", recent commits have grown multi-paragraph essays —
ten lines on `15e4193`, nine on `a4d7993`, eight on `ac42a40` — that restate what the change's
`proposal.md`, `design.md` and the ADRs already say. The reasoning ends up in three places, one of
which is the hardest to find and the most expensive to change.

## What Changes

- **Remove the mandatory-commit phrasing** from `AGENTS.md`, `CONTRIBUTING.md`, `README.md`,
  `docs/PROMPTS.md` and the six `docs/agentic/` documents. Every rule that says work *is* a commit, or
  that an edit must land *in the same commit*, is re-anchored to the change, the task or the tree it
  actually describes.
- **Keep the factual mentions.** "The committed eval corpus", the pinned `uv.lock`, the pre-commit
  hook, and the rule against committing `.env` or `.cache/` describe how the repository is, or what
  must never be published — not an instruction to commit. They stay. Only two phrasings of the
  secrets rule are reworded so the prohibition reads as a prohibition and not as a commit step.
- **Commit messages are subject-only by default.** `type(scope): summary` and nothing else. A body is
  written only when the user explicitly asks for one. `CONTRIBUTING.md` states the rule;
  the commit skill's message section is narrowed to match.
- **The reasoning gets one home per decision.** An architectural decision's reason belongs in its ADR,
  a behaviour's in the change's OpenSpec artifacts, and a rule's in the document that owns it — never
  only in a commit message. The two rules that currently require the reason *in the commit message*
  are rewritten to point at the ADR or the task instead.
- **Keep `.agents/skills/commit/SKILL.md`.** The skill is not deleted and its purpose, ordering,
  staging, safety-gate and ambiguity steps are untouched. Only its message-writing step changes, to
  make the short message the default rather than an option.

Not in this change: any behaviour of the `numenews` package. `src/`, `tests/`, `pyproject.toml`,
`Makefile`, `uv.lock` and both capabilities are untouched.

## Capabilities

### New Capabilities

None. This change edits contributor and agent guidance. It introduces no capability whose behaviour
could be observed from outside the repository.

### Modified Capabilities

None. `mcp-surface` (the nine MCP tools) and `cli-surface` (the six CLI commands) describe the product,
not the workflow. `.openspec.yaml` sets `skip_specs: true` for that reason — no requirement is invented
to satisfy validation.

## Impact

- **Edited** (9 files):
  - `AGENTS.md` — three rules: the atomic-commit bullet, the spec-delta bullet's "in the same commit",
    and "keep commits conventional".
  - `CONTRIBUTING.md` — workflow step 3; the `## Commits` section gains the subject-only rule.
  - `README.md` — the contributing summary's "one atomic commit".
  - `docs/PROMPTS.md` — the prompt-changing step that cites `AGENTS.md` for "the doc in the same commit".
  - `docs/agentic/AGENT_WORKFLOW.md` — loop step 3 and the tick-the-task step (step 5).
  - `docs/agentic/CONVENTIONS.md` — the `## Commits and tests` atomic-commit paragraph.
  - `docs/agentic/EVAL_OF_AGENT.md` — the "same change" section, the commit-message-carries-the-reason
    sentence, and two checklist items.
  - `docs/agentic/GUARDRAILS.md` — five rules: the same-commit dependency comment, the reason in the
    commit message, the test-weakening rule, the `tasks.md` item, and the two secrets clauses.
  - `docs/agentic/PROMPTING_PLAYBOOK.md` — the "keep the commit atomic" rule, the plan prompt's
    "conventional commit message" output item, the implement prompt's atomic-commit closing, and the
    anti-pattern that names splitting a commit.
  - `docs/agentic/TOOLING.md` — the comment in the worked example's numbered steps.
- **Left alone on purpose**: `docs/STACK.md`'s pre-commit row is a fact about the hook, and the
  factual mentions elsewhere (the committed eval corpus, `docs/eval_report.md`, `uv.lock`,
  `.cursor/mcp.json`) describe the repository rather than instructing anyone.
- **Narrowly edited**: `.agents/skills/commit/SKILL.md` — step 4 only. Not deleted; no other step
  changes.
- **Unchanged**: `src/`, `tests/`, `pyproject.toml`, `Makefile`, `docker-compose.yml`, `uv.lock`,
  `openspec/specs/`, all ADRs (frozen records), and every file under `openspec/changes/archive/`
  (frozen history).
- **Gate**: `make lint` and `make test` are unaffected — no source file changes. The docs must still
  read as complete rules after the edits, which is what the verification sweeps.
