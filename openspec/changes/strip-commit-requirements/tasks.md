# Tasks

## 1. Re-anchor the source documents

- [x] 1.1 In `AGENTS.md`, replace the atomic-commit bullet under `## OpenSpec` (line 55) with a
      task-level rule — one `tasks.md` item is one atomic task, its checkbox ticked as part of that
      task — and rewrite the spec-delta bullet under `## When changing code` (line 85) so the
      requirement is that the owning requirement and the `tasks.md` item are updated together with the
      work, not "in the same commit". Delete the `Keep commits conventional` bullet (line 90) from
      `## When changing code`, since the message format is owned by `CONTRIBUTING.md` and task 2.1
      states it there. Verify by reading both sections whole: every rule still reads as a complete
      instruction, and `grep -n -i commit AGENTS.md` returns no line that tells anyone to commit.
      **Deviation:** every box in this file was written as `- [x]` while the change was being
      proposed, before any of the work existed. All fourteen were reset to `- [ ]` and the tree was
      verified untouched (`git status --short` showed only this change directory) before
      implementation started, so no box here records work that did not happen.
- [x] 1.2 In `CONTRIBUTING.md`, rewrite workflow step 3 (line 15) from "one `tasks.md` item per atomic
      commit, ticked in the same commit" to one atomic task per item with its checkbox ticked as part
      of it. In the `## Commits` section, add the message rule: `type(scope): summary` and no body;
      a body is written only when the user explicitly asks for one. Leave the conventional types, the
      scope list, the imperative-mood and 72-character guidance, and the three examples unchanged.
      Verify: `grep -n '^## ' CONTRIBUTING.md` still lists `## Commits`, the numbered workflow still
      reads 1–4 with no gap, and the new rule names the no-body default in one sentence.
- [x] 1.3 In `README.md`, reword the contributing summary (line 205) so the short version reads "one
      `tasks.md` item is one atomic task" instead of "one atomic commit". Verify: `grep -n -i "atomic"
      README.md` returns only the reworded line, and the sentence still reads as a complete summary of
      the workflow with `make lint && make test` as the gate.

## 2. Re-anchor the agent workflow documents

- [x] 2.1 In `docs/PROMPTS.md`, reword step 2 of `## Changing a prompt` (line 320) so it states that
      the matching section is updated as part of the prompt change, instead of citing `AGENTS.md` for
      a doc that changes "in the same commit". Confirm the citation is accurate afterwards: `AGENTS.md`
      requires `docs/PROMPTS.md` to be updated when a prompt changes, and it no longer phrases that as
      a commit. Verify: `grep -n -i "same commit" docs/PROMPTS.md` returns nothing, and the step still
      names the file to update and why.
- [x] 2.2 In `docs/agentic/AGENT_WORKFLOW.md`, rewrite loop step 3 (lines 15–17) so a `tasks.md` item is
      one atomic task rather than one conventional commit, and step 5 (line 21) so the checkbox is
      ticked as part of the task rather than "in the same commit". Keep the stop-and-update-the-change
      clause and the deviation note. Verify: `grep -n -i commit docs/agentic/AGENT_WORKFLOW.md` returns
      no line instructing anyone to commit, and the seven-step loop still reads as seven complete
      steps.
- [x] 2.3 In `docs/agentic/CONVENTIONS.md`, rewrite the `## Commits and tests` paragraph (lines 128–132)
      so the atomic unit is the `tasks.md` item, with the code, tests, docs and ticked checkbox landing
      together. Keep the conventional-commit format sentence that defers to `CONTRIBUTING.md` — that is
      the pointer task 1.2 relies on — and keep the "a change that needs two subjects is two tasks"
      clause. Verify: `grep -n -i -E "atomic commit|same commit" docs/agentic/CONVENTIONS.md` returns
      nothing, and the section heading `## Commits and tests` still matches what it covers.
- [x] 2.4 In `docs/agentic/TOOLING.md`, change the numbered step in the worked example (line 134) from
      "tick the checkbox, update the docs, one atomic commit" to "tick the checkbox, update the docs"
      so the example stops ending in a commit instruction. Verify: read steps 1–4 as a sequence and
      confirm each is an action the reader performs, with step 4 still archiving the change.

## 3. Rewrite the guardrails that used the commit boundary as their mechanism

- [x] 3.1 In `docs/agentic/GUARDRAILS.md`, re-anchor the five rules whose `*Instead:*` clauses depend on
      "in the same commit": the dependency comment (line 83) becomes "the same change"; the
      superseded-test reason (line 90) moves out of the commit message into the ADR and the task, so
      the sentence no longer names a commit at all; the `tasks.md` item (line 121) becomes "the same
      change"; and the two secrets clauses (lines 110–114) are reworded so the prohibition stands on its
      own — `.env` and `.cache/` are never published, `.env.example` is what changes when a variable is
      added — without phrasing either as a commit step. Verify: read each edited rule's `*Why:*` and
      `*Instead:*` together and confirm the instruction is still complete; then
      `grep -n -i commit docs/agentic/GUARDRAILS.md` and confirm every remaining hit is a prohibition
      or a fact, with none requiring a commit.
- [x] 3.2 In `docs/agentic/EVAL_OF_AGENT.md`, rewrite the `## Check the paperwork landed in the same
      change` section (lines 56–58) so one `tasks.md` item is one atomic task whose deliverable holds
      the ticked checkbox, the named docs and any ADR together; replace the "the commit message carries
      the reason" sentence (line 53) with the ADR and the `tasks.md` deviation note as where the reason
      is recorded. Update the two checklist items (lines 115 and 119) to match — the paperwork check
      and an atomicity check that does not require a commit. Verify: the four edited passages name no
      commit as a requirement, and the checklist still lists eight items, each checkable from the tree
      alone.
- [x] 3.3 In `docs/agentic/PROMPTING_PLAYBOOK.md`, edit the four sites that instruct a commit: the
      "keep the commit atomic" rule under `## Rules that hold for every prompt` (lines 18–19) becomes a
      rule that the task's deliverable is one coherent unit with the ticked box, dropping "ask for a
      tree ready to commit once"; the plan prompt's output item 5 (line 42) asks for the scope the task
      belongs to rather than a commit message; the implement prompt (line 59) asks for a tree that
      stands alone; and the anti-pattern (lines 142–143) warns against turning one task into three
      unrelated ones. Leave the "if the work is larger than one atomic commit, propose the split in
      tasks.md" fallback (line 43) in place — it stops a task outgrowing its spec delta. Verify:
      `grep -n -i -E "atomic commit|ready to commit|commit nothing" docs/agentic/PROMPTING_PLAYBOOK.md`
      returns only line 43's split fallback, and each prompt still reads as paste-ready text whose
      numbered deliverables are all obtainable without committing.

## 4. Narrow the commit skill's message rule

- [x] 4.1 In `.agents/skills/commit/SKILL.md`, change step 4's body guidance so the default is
      `type(scope): summary` with no body, and a body is written only when the user explicitly asks for
      one; replace the "a body only when the *why* is non-obvious" sentence and keep the types, scopes,
      imperative-mood, 72-character, no-trailer and no-attribution rules unchanged. Update step 2's
      OpenSpec bullet (line 36) so it no longer cites `AGENTS.md` for "one atomic commit per `tasks.md`
      item", which task 1.1 removes. Do not delete the file and do not touch steps 1, 3, 5, 6, 7, 8 or
      9, or the guardrails. Verify: `grep -n -i -E "atomic commit|same commit" .agents/skills/commit/SKILL.md`
      returns only step 6's generated-files rule, the frontmatter is unchanged, and the nine steps are
      all still present.

## 5. Verify the tree

- [x] 5.1 Sweep every tracked markdown file for mandatory-commit phrasing:
      `git grep -n -i -E "atomic commit|same commit|in its own commit|ready to commit|one commit|commit nothing|per commit" -- '*.md'`.
      Every remaining hit must be classified as a fact or a prohibition, one by one, with the
      classification recorded in the report; hits under `openspec/changes/archive/` and in this
      change's own artifacts are expected, because a change that removes a convention has to name it.
      Verify: the command's full output is read and each hit is attributed, and no hit outside the
      archive and this change tells a reader that work requires a commit.
      **Deviation:** the sweep excludes part of the tree, so it missed two sites the broader
      `\bcommit\b` pass found, both added to tasks 2.4 and 3.3: `PROMPTING_PLAYBOOK.md`'s wrapped
      "fold a second change into the same commit" (its line 14 carried no keyword of its own) and
      `TOOLING.md`'s "the gate every commit has to pass". Both are the same defect and are fixed.
      Final non-archive hits: `docs/STACK.md:64` (the pre-commit hook is a fact), the commit skill's
      step 6 generated-files rule (a fact about the skill), and `openspec/changes/archive/`.
- [x] 5.2 Confirm the facts were left intact rather than swept away: `docs/STACK.md`'s pre-commit row,
      the committed `uv.lock` and `docs/eval_report.md` references, and the secrets prohibition are all
      still present. Verify: `git grep -n -i -E "pre-commit|committed corpus|uv.lock|eval_report" --
      '*.md'` returns the factual hits and none of them was reworded, and the secrets rule still
      forbids publishing `.env` and `.cache/`.
- [x] 5.3 Run the gate and confirm a docs-only change left it untouched: `make lint` and `make test`
      pass, `openspec validate "strip-commit-requirements" --strict` passes, and `git status --short`
      shows only the intended files. Verify: each command's own output is pasted, the test count
      matches the pre-change baseline, and the changed-file list contains no file under `src/`,
      `tests/`, or `openspec/changes/archive/`.
      **Deviation:** the count does not match the number named above — the task inherited
      "677 passed / 8 skipped" from a previous change's record, and the baseline at this HEAD
      (`2e7c427`) is **682 passed / 8 skipped** with the same 100/99/100 floors. The work cannot have
      moved it: no test asserts on the edited phrases, and the two files that name `AGENTS.md`
      (`tests/eval/judge.py`, `tests/unit/test_numerology_api.py`) cite it in docstrings only. The
      correct baseline is recorded here rather than the number the task predicted.
      **Deviation:** eleven files were edited, not the nine the proposal lists. The two extra are
      `docs/agentic/PROMPTING_PLAYBOOK.md`'s wrapped bullet line and `docs/agentic/TOOLING.md`'s gate
      sentence, both found by the broader sweep in 5.1. Each is the same defect in an already-edited
      file; neither adds scope.
