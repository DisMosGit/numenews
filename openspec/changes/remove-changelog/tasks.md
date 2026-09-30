# Tasks

## 1. Stop asking contributors to maintain a changelog

- [x] 1.1 In `CONTRIBUTING.md`, delete pull-request step 3 ("Update `CHANGELOG.md` under
      `[Unreleased]` if user-facing") and renumber the remaining steps 1–4; re-anchor "Where the old
      roadmap went" (line 33) so it names `git log`, the `v0.1.0` tag and the archived change instead
      of the deleted file; add a short `## Releases` section stating that a release is a tag, its
      content is `git log`, the pre-0.2 history is at `git show v0.1.0:CHANGELOG.md`, and there is
      deliberately no changelog. Verify: `grep -n '^## ' CONTRIBUTING.md` shows `## Releases`, the
      pull-request list reads 1–4 with no gap, and the documented recovery command runs and prints
      the `[0.1.0]` entry.
- [ ] 1.2 In `docs/agentic/`, remove every changelog instruction: `AGENT_WORKFLOW.md` step 6 (23–25,
      keep the ADR half), `EVAL_OF_AGENT.md` (61 and 116), `PROMPTING_PLAYBOOK.md` (64 and 83) and
      `TOOLING.md` (134). Verify: `git grep -ni changelog -- docs/` returns nothing, and each edited
      sentence still reads as a complete rule — the ADR clause in `AGENT_WORKFLOW.md`, and the
      "checkbox, the named docs and any ADR are in the same commit" list in `EVAL_OF_AGENT.md`.

## 2. Delete the changelog

- [ ] 2.1 Delete `CHANGELOG.md` with `git rm`, in a commit that contains nothing else. Verify:
      `test ! -e CHANGELOG.md` succeeds and `git show --stat HEAD` lists exactly one file, as a
      deletion.

## 3. Verify the tree

- [ ] 3.1 Sweep tracked files for the dead file name: `git grep -ni changelog` must return hits only
      under `openspec/changes/archive/`, plus the single recovery command in `CONTRIBUTING.md`.
      Verify: the command's full output is read and every hit is attributed to one of those two.
- [ ] 3.2 Confirm nothing reads the file: no `Changelog` key under `[project.urls]` in
      `pyproject.toml`, and no version or release badge in `README.md`. Verify: both files' grep
      output is read, and any hit is classified as unrelated.
- [ ] 3.3 Run the full gate and confirm a docs-only change left it untouched: `make lint` and
      `make test` pass, `openspec validate "remove-changelog" --strict` passes, and `git status
      --short` is clean. Verify: each command's own output is pasted, and the test count matches the
      677 passed / 8 skipped baseline.
