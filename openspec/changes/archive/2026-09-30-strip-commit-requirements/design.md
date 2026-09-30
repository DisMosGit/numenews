# Design

## Context

See `proposal.md` — Why. Three properties of the current tree shape the approach.

1. **The rules are layered, and the same rule is restated at several layers.** `AGENTS.md` is the
   source for agents, `CONTRIBUTING.md` for humans, and `docs/agentic/` expands both. "One atomic
   commit per `tasks.md` item" appears in all three layers, in five files, with slightly different
   wording each time. Removing it means editing every restatement, not just the source.
2. **`GUARDRAILS.md` uses the commit boundary as a *mechanism*, not only as a requirement.** Five of
   its rules end in an `*Instead:*` clause whose teeth come from "in the same commit" — the dependency
   comment, the superseded test, the `tasks.md` item, and the two secrets clauses. Deleting the phrase
   without replacing the mechanism leaves rules that say what to do and no longer say when it is too
   late.
3. **Two statements look like commit rules and are not.** `Do not commit .env or .cache/` is a
   publication prohibition, and the factual mentions — the committed eval corpus, the pinned
   `uv.lock`, the pre-commit hook — describe the repository. A blanket sweep for the word "commit"
   would break rules that must stay, which is why this change is scoped by kind of sentence rather
   than by keyword.

## Goals / Non-Goals

**Goals:**

- Every remaining commit mention in the tree is either a fact about the repository or a prohibition on
  publishing something — never an instruction that work requires a commit.
- Each rule that used the commit boundary as its mechanism still says, completely and in one sentence,
  what has to be true together.
- The commit-message rule is stated once, and the commit skill agrees with it.
- A reader of the diff can tell, for every deleted line, which of the two kinds it was.

**Non-Goals:**

- Changing the commit *format* rules. `CONTRIBUTING.md`'s `## Commits` section — conventional types,
  the scope list, the imperative-mood and 72-character rules, the examples — is accurate and stays
  apart from one added rule.
- Touching the branch or pull-request guidance. It describes human contribution, where a branch and a
  PR are real; it does not tell an agent to commit.
- Reducing the commit skill to a message helper. Ordering, grouping, explicit staging (`git add -p`,
  no `git add -A`), the safety gate, the never-rewrite-history and never-push guardrails, and the
  stop-and-ask step all remain exactly as they are.
- Re-editing history, archived changes, or ADRs. They record what was decided then.

## Decisions

### D1 — Scope by sentence kind, not by keyword

**Chosen:** three kinds. **(a) Mandatory-commit phrasing** — a sentence that tells someone to commit,
to commit at a specific moment, or that defines a unit of work as a commit — is re-anchored.
**(b) Facts** — the committed eval corpus, the committed `docs/eval_report.md`, the committed
`uv.lock`, the committed `.cursor/mcp.json`, the pre-commit hook — are left alone.
**(c) Prohibitions** — publishing `.env`, `.cache/`, secrets — are left alone as rules, with the two
clauses that are phrased as "do not commit X *in a commit*" reworded so the prohibition stands on its
own.

**Alternatives considered:** removing every occurrence of the word "commit"; leaving the docs and
changing only the commit skill.

**Why:** the keyword sweep fails on its first file — it deletes the secrets prohibition and the
pre-commit hook description, which are the two places the word is load-bearing. Changing only the
skill fails differently: the skill is invoked when someone *wants* a commit, so it is not what makes
committing feel mandatory; the docs are. The mechanism has to be removed where it is stated.

### D2 — Re-anchor to the change, the task and the tree

**Chosen:** "one atomic commit per `tasks.md` item" becomes **one atomic task per `tasks.md` item** —
the item is the unit, completed at once, whether or not anything is committed. The tick-off, the named
docs and the ADR are required **together with the work**, not "in the same commit". "The same commit"
in `GUARDRAILS.md`'s five rules becomes "the same task", "the same change" or "the same pass", whichever
the rule is actually about.

**Alternatives considered:** deleting the phrases without replacement; replacing them with "in the
same session".

**Why:** deleting them leaves the rules toothless — "update the dependency comment" with no statement
of when, which is how it drifts. "Same session" is machine-specific and means nothing to a human
contributor. "Same task" preserves both the atomicity intent and the co-location requirement, and it
is the vocabulary `CONTRIBUTING.md`, `AGENT_WORKFLOW.md` and the change artifacts already use.

### D3 — Subject only, stated once, mirrored in the skill

**Chosen:** `type(scope): summary` — no body — unless the user explicitly asks for one.
`CONTRIBUTING.md`'s `## Commits` section states the rule, since `CONVENTIONS.md` already defers to it
("Commits follow Conventional Commits (../../CONTRIBUTING.md)") and that deferral keeps one home. The
commit skill's step 4 mirrors the rule in the place that actually writes messages.

**Alternatives considered:** a word or line cap instead of a prohibition; leaving the skill's
"when the *why* is non-obvious" wording and changing only the docs.

**Why:** the two documents currently disagree — a body when the reason is non-obvious (skill) versus
the reason in the commit message (guardrails) — and an agent resolves that disagreement by writing the
longer one. A rule with one wording cannot conflict. A cap would let the ten-line bodies that
motivated this change stay legal at eight lines; the skill keeps the `-m "<body>"` mechanism for the
case the user asks.

### D4 — The reason gets one home per decision kind

**Chosen:** an architectural decision's reason lives in its ADR; a behaviour's lives in the change's
OpenSpec artifacts; a rule's lives in the document that owns the rule. The two rules that currently
require the reason *in the commit message* — `GUARDRAILS.md`'s superseded-test rule and
`EVAL_OF_AGENT.md`'s sentence on intentional test changes — are rewritten to point at the ADR, the
task, and `tasks.md`'s deviation note.

**Why:** the commit message was the only home that requires reading `git log` to find, and the only
one that cannot be edited later. Every other home is a file in the tree, which is what the
documentation already calls the source of truth.

### D5 — One thing in the checklist that is not a commit reference

The plan prompt in `PROMPTING_PLAYBOOK.md` asks for "the conventional commit message, including the
scope" as a plan deliverable, and the implement prompt asks for the work to be "ready as one atomic
commit". Both survive as instructions to commit. They are replacements, not deletions: the plan asks
for the **scope** the task belongs to, which is real planning information that the scope list in
`CONTRIBUTING.md` defines, and the implement prompt asks for a **tree that stands alone**, which is
the atomicity property worth keeping. The commit-splitting fallback ("if the work is larger than one
atomic commit, propose the split in `tasks.md`") stays as it is — it keeps a task from growing past
its spec delta, which is the guardrail the sentence actually enforces.

**Why:** these are edits to prompts an operator pastes verbatim. Rewriting them to drop the information
entirely would lose a useful planning step in the name of removing a word.

## Risks / Trade-offs

- **A stale instruction survives** → verification greps every tracked file for the mandatory phrasings
  (`atomic commit`, `same commit`, `ready to commit`, `in its own commit`) and requires each remaining
  hit to be a fact or a prohibition, classified one by one.
- **A rule loses its teeth** → each edited `*Instead:*` clause is read back as a complete sentence
  against its `*Why:*`, and the task list names which six they are rather than saying "update
  guardrails".
- **Only half the restatements are edited**, since the same rule sits in several files → the task list
  names the file and the sentence for each, and the sweep is run against the whole tree rather than
  the edited files.
- **The commit skill is misread as deleted or gutted** → it is edited in step 4 alone, and the proposal
  and the task both say so explicitly.
- **An agent reads "no commit" as "no atomicity" and starts batching tasks** → the task-level rule
  stays in both `AGENTS.md` and `AGENT_WORKFLOW.md`, and the verification reads the edited paragraphs
  whole rather than by diff.
- **The archived `adopt-openspec-workflow` decision still names the old convention** → it is frozen and
  stays frozen, exactly as it still names `CHANGELOG.md` after the previous change. The live
  consequence is that one archived sentence describes a convention the tree no longer has; the
  proposal's successors state the current one.

## Migration Plan

Documentation and prompts only; nothing to deploy, and rollback is `git revert`. The order is by
blast radius: `AGENTS.md` first, since it is the source the other documents restate; then
`CONTRIBUTING.md`, which gains the one new rule and is what `CONVENTIONS.md` defers to; then the five
`docs/agentic/` files; then the commit skill's step 4; then `README.md`. No spec deltas land at archive
time, since `.openspec.yaml` sets `skip_specs: true` and both capabilities are untouched.
