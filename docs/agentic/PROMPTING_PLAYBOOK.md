# Prompting playbook

> Paste-ready prompts for an operator driving an agent here, one per kind of work, each
> naming the context to include and the output to expect. The rules they assume are in
> [`AGENT_WORKFLOW.md`](AGENT_WORKFLOW.md); the review behind prompt 3 is
> [`EVAL_OF_AGENT.md`](EVAL_OF_AGENT.md); the style to match is in [`CONVENTIONS.md`](CONVENTIONS.md).

## Rules that hold for every prompt

- **Name the change and the `tasks.md` item** (`adopt-openspec-workflow`, item 4.2) and quote what
  that item says it verifies. A prompt without a change is a request for unsupervised refactoring.
- **Work only inside the change.** If the work is not covered by the change's spec deltas, stop and
  update the artifacts — do not widen the change to fit, and do not fold a second change into the
  same commit.
- **Require the exact commands and their observed output**, and **forbid weakening a test** in the
  prompt itself: "it should pass" is not evidence, and deleting an assertion or adding a `skip` to
  get green is a rejected change. An intentional test change states its reason.
- **Keep the commit atomic.** One `tasks.md` item is one conventional commit with the code, its tests,
  the docs and the ticked box; if the agent is not the committer, ask for a tree ready to commit once.
- **Treat `.docs/plan.md` as context only.** Where it disagrees with `AGENTS.md` or
  `openspec/specs/`, those win.

## 1. Plan a change's task

*Context:* the change name, the `tasks.md` item, the requirement or scenario it serves, and the
"why" from the change's `proposal.md`.

```text
You are working in the numenews repository. Do not edit anything yet.

Change: openspec/changes/<change-name>/.
Task: <item number and text, quoted from tasks.md>.
Serves: <requirement name from the change's spec delta, or "process only, no behaviour">.

Read AGENTS.md, CONTRIBUTING.md, the change's proposal.md, design.md and tasks.md, and the docs
the task names.
Produce a plan with, in order:
1. the goal in one sentence, and the task's stated verification as a checklist of commands;
2. every file to create or change, one line of why each;
3. the exact verification commands, and the output you expect from each;
4. risks: which boundary or invariant this touches, and what could break silently;
5. the conventional commit message, including the scope.
If the work is larger than one atomic commit, propose the split in tasks.md instead.
```

*Expected:* plan text only — no edits. Approve it before running prompt 2.

## 2. Implement a task to its verification

*Context:* the approved plan, the change's spec deltas, and the layer docs
([`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`../MCP_TOOLS.md`](../MCP_TOOLS.md),
[`../USER_FLOW.md`](../USER_FLOW.md), [`../EVAL.md`](../EVAL.md)).

```text
Implement task <n> of openspec/changes/<change-name>/ exactly as planned. Do not change scope.

Follow docs/agentic/CONVENTIONS.md and docs/agentic/GUARDRAILS.md. Do not weaken, skip or
delete a test. Do not add a dependency the task does not need. Keep the change ready as
one atomic commit (commit nothing unless the task says so).
Before reporting done, run and paste the exact output of:
  uv run ruff check . && uv run ruff format --check . && uv run mypy .
  uv run pytest tests/unit tests/integration -v
  <task-specific command, e.g. make test-eval, or make dev plus a health check>
Then tick the task's checkbox in tasks.md, update CHANGELOG.md under [Unreleased] if
user-facing, update the docs the task names, and add an ADR if the decision is architectural.
Report: files changed; each command with observed output; deviations and their reason.
```

*Expected:* a diff that matches the plan, plus the command transcript. Re-run the commands yourself.

## 3. Review an agent's diff

*Context:* the change name, the task item, the diff (or base revision), and the implementer's report.

```text
Review the diff for task <n> of openspec/changes/<change-name>/ against what the task says it
verifies. Do not edit.

Read docs/agentic/EVAL_OF_AGENT.md first. For each point, state pass or fail with evidence:
- every verification the task names, checked by running its command — your own output, not the
  other agent's summary;
- tests/ diff read line by line for removed, skipped or weakened assertions;
- docs/, docs/adr/, CHANGELOG.md and the change's own artifacts updated in the same change;
- failure paths: LLM endpoint down or unset, empty collection, duplicate ingest, 4xx/5xx source;
- factual claims in new docs checked against the code.

Output a findings list — file:line, severity, concrete fix — and a verdict. Do not rewrite
the change; the verdict and findings are the deliverable.
```

*Expected:* a verdict backed by your own command output, not a restatement of the implementer's report.

## 4. Write an ADR

*Context:* the decision, the alternatives considered, the change that made it.

```text
Read docs/adr/template.md and one existing ADR for voice (docs/adr/0011 or 0013).

Write docs/adr/NNNN-<slug>.md for this decision: <one sentence>. Alternatives: <...>.
Use the template's sections exactly (Status, Date, Context, Decision, Consequences,
References). "Decision" speaks in the active voice ("We will …") and states its scope.
"Consequences" says what gets easier, what gets harder and what is ruled out. Record the
reason, never only the change. Take the next free number and date it today, and link the
ADR from the change's design.md and from the docs page that now owns the decision.
```

*Expected:* one new file under `docs/adr/` matching the template, plus the links to it.

## 5. Diagnose a failing check

*Context:* the exact command, its full output (not a paraphrase), the last change, and whether it
reproduces on a clean tree.

```text
This check fails. Do not guess and do not change code yet.

Command: <exact command>
Observed output: <paste in full, including the traceback or assertion diff>
Last change: <commit subject or change name>. Reproduces on a clean checkout: yes/no.

Work in order:
1. Reproduce the command and paste its output.
2. Name the first failing assertion or error and the code path that reaches it.
3. State the root cause, with the file:line you read to confirm it.
4. Propose the minimal fix. If the failure is a test encoding a superseded decision, say so
   and propose the deliberate test change with its reason — never a weakened assertion.
5. Give the exact command to re-run and its expected output.
```

*Expected:* a root cause and a minimal, explained fix — or an environment diagnosis (Qdrant not up,
no LLM endpoint, no model weights) with the command that proves it.

## Anti-patterns

- **The vague prompt.** "Improve the docs", "clean up the code", "make it faster" asks for
  unsupervised re-scoping. Name the change and the task, or propose a change first.
- **Accepting the summary.** A report that says `make test` passed is not evidence; the output is.
  Re-run it. An agent that stopped at "should be fine" has not finished.
- **Letting the agent re-scope the change.** Moving the verification, dropping a task or merging two
  changes to make the work fit changes the plan, not an implementation detail.
- **Asking for improvements instead of a task.** "Also refactor this while you're there" turns one
  atomic commit into three unrelated ones and makes the diff unreviewable.
- **Letting the agent mark its own homework.** Self-review is not review; the verdict comes from
  re-running the commands the task names, and a traceback pasted without its command hides the
  invocation that produced it.
