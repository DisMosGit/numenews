# Tasks

## 1. Make OpenSpec the source of truth in the process documents

- [x] 1.1 Rewrite `AGENTS.md`: replace the "Roadmap" section with the OpenSpec workflow (propose →
      apply → archive, `openspec/specs/` for built behaviour, `openspec/changes/` for work in flight),
      and re-point the "When changing code" and "Commands" bullets that name phases. Verify:
      `grep -n ROADMAP AGENTS.md` returns nothing, and the file names `openspec/` in the Rules section.
- [x] 1.2 Rewrite the loop in `docs/agentic/AGENT_WORKFLOW.md` and the "do not invent a roadmap task"
      entry in `docs/agentic/GUARDRAILS.md` so the unit of work is an OpenSpec change and a `tasks.md`
      item rather than a phase task with a Definition of Done. Verify: neither file mentions a roadmap
      task id or a phase gate, and both name the archive step.
- [x] 1.3 Rewrite `docs/agentic/PROMPTING_PLAYBOOK.md`: every prompt that says "name the task by its
      `ROADMAP.md` id" instead names the change and its `tasks.md` item, and the prompts that read
      "`ROADMAP.md` (the phase)" read the change's `proposal.md`/`design.md`/`tasks.md`. Verify: all
      five prompts reference an OpenSpec artifact and the file mentions no phase.
- [x] 1.4 Re-point the remaining roadmap citations in `docs/agentic/CONVENTIONS.md`,
      `docs/agentic/EVAL_OF_AGENT.md` and `docs/agentic/TOOLING.md`, including the review checklist in
      `EVAL_OF_AGENT.md` and the coverage-floor comments in `TOOLING.md`. Verify:
      `grep -rnE 'ROADMAP|[Pp]hase' docs/agentic/` returns nothing.
- [x] 1.5 Verify the group: `grep -rnE 'ROADMAP|[Pp]hase' AGENTS.md docs/agentic/` returns
      nothing and `make lint` passes. Land as one commit.

## 2. Re-target citations in documentation

Both sweeps in this group match `/[Rr]oadmap|[Pp]hase/`, case-insensitively. The citations come in
three casings — `ROADMAP 7.4` in test docstrings, `Roadmap 5.3` in source docstrings, `roadmap 3.8`
in prose — so a case-sensitive pattern silently misses two thirds of them. The pattern also catches a
bare phase number (`(phase 8.3)`), a phase-qualified noun ("the MCP tools of phase 6") and a bare "the
phase that needs it", per design D11 — plus bare roadmap task ids like `(4.2)`, which contain neither
word and are found with `\([0-9]{1,2}\.[0-9]{1,2}\)`. Four surfaces keep their phase vocabulary and
their in-body "the roadmap" as a plain noun: `docs/adr/` (decision rationale, which D5 freezes),
`CHANGELOG.md`, the "How it was built" narrative at the end of `docs/ARCHITECTURE.md`, and
`tests/eval/fixtures/news.jsonl`, which is retrieved article text rather than prose about the project.
The dead **filename** is stricter than the vocabulary: `ROADMAP.md` survives only in the two places
that document the deletion itself, `CONTRIBUTING.md` and `CHANGELOG.md`. Run the sweeps with
`git grep`, which searches tracked files only; a plain `grep -r .` also walks `.venv/`, `.venv-eval/`
and `__pycache__/` and buries a clean result in noise.

- [x] 2.1 Rewrite the "`ROADMAP.md` is the authoritative status" headers and in-body citations across
      `docs/` (31 files), mapping each phase to its owning page per the table in `design.md` D2 — for
      example `docs/QDRANT_COLLECTIONS.md` and `docs/EMBEDDINGS.md` for phase 3, `docs/RAG_PIPELINE.md`
      for phase 5. This covers the bare phase numbers as well: doc-header provenance (`> Phase 3.`),
      inline cross-references (`(phase 8.3)`) and phase-qualified nouns ("the MCP tools of phase 6")
      all become the owning page or capability name. Verify:
      `grep -rnE 'ROADMAP|[Pp]hase' docs/ --exclude-dir=adr | grep -v 'ARCHITECTURE.md'`
      returns nothing.
- [x] 2.2 Correct every roadmap reference in `docs/adr/`: the nine References / "See also" links to
      the owning docs pages, and each in-body mention reworded only as far as the dead file name
      ("`ROADMAP.md` 1.1 additionally places …" → "Phase 1 additionally places …"). Decision text,
      rationale and alternatives are unchanged, and the phase numbers stay. Verify: `git diff
      docs/adr/` changes nothing but how the roadmap is named — no decision, alternative or
      consequence is reworded — and `grep -rn ROADMAP docs/adr/` returns nothing.
- [x] 2.3 Replace the "What is built, in what order?" row in `docs/ARCHITECTURE.md` with
      `openspec/specs/`, re-point its in-body "authoritative status" sentence, and drop the phase tags
      from the component list near the top (`numenews.mcp, phase 6` and the two beside it). The "How it
      was built" narrative at the end of the file is history and stays as it is (design D11). Verify:
      the summary table has no roadmap entry, the new target exists, and
      `grep -nE 'ROADMAP|[Pp]hase' docs/ARCHITECTURE.md` returns only lines from that narrative.
- [x] 2.4 Re-anchor the coverage floors currently cited as "ROADMAP 10.4" to
      `docs/coverage_report.md` in `docs/coverage_report.md` itself, `docs/FAQ.md` and
      `docs/TESTING.md`, and re-point the `docs/FAQ.md` "phases 0–10 are planned there" answer at the
      OpenSpec workflow. Verify: both files describe the floors without naming a phase.
- [x] 2.5 Add a line to `docs/MCP_TOOLS.md` and `docs/USER_FLOW.md` naming `mcp-surface` and
      `cli-surface` as authoritative for behaviour, keeping the client-setup snippet and its link to
      the committed `.cursor/mcp.json` intact. Verify: every relative link in both files resolves, and
      both name their capability.

## 3. Re-target citations in tests and source

- [x] 3.1 Rewrite the roadmap citations in `tests/unit/` — the ~34 that name `ROADMAP` and the bare
      phase numbers alongside them — as capability names or owning docs pages — for example `ROADMAP 1.2`
      becomes `docs/NUMEROLOGY.md` and `ROADMAP 7.4` becomes `cli-surface`. Verify:
      `grep -rnE 'ROADMAP|[Pp]hase' tests/unit/` returns nothing and `git diff` touches
      docstrings and comments only.
- [x] 3.2 Rewrite the roadmap citations in `tests/integration/` the same way, including the
      "nine tools of ROADMAP 6.2-6.10" comment in `test_mcp_stdio.py` and the fixture note in
      `conftest.py`. Verify: `grep -rnE 'ROADMAP|[Pp]hase' tests/integration/` returns nothing.
- [x] 3.3 Re-point the roadmap references in `src/numenews/` — five that name `ROADMAP`
      (`__init__.py`, `cli/main.py`, `vector/history.py`, `models/forecasts.py`, `agents/extract.py`)
      plus the ~66 bare phase numbers spread across `vector/`, `mcp/`, `agents/`, `pipeline/`,
      `models/`, `cli/`, `numerology/` and `news/` — at the owning docs page or capability name.
      Verify: `grep -rnE 'ROADMAP|[Pp]hase' src/` returns nothing.
- [x] 3.4 Verify no behaviour moved. Two checks, because a diff review is not enough on 100+ files:
      (a) `uv run pytest tests/unit tests/integration` passes with the same count as before the edits;
      (b) an AST comparison per changed file — parse `git show HEAD:<file>` and the working copy,
      strip docstrings from both, and compare `ast.dump`. Every changed file must come back identical.
      (b) is what actually proves the claim: it cannot be fooled by a reflowed line or a plausible
      looking edit, which is exactly the risk in 71 test docstrings.
      Four exceptions are sanctioned, and no others:
      * two test *names* that contain a phase word — `test_the_phase_surface_is_exactly_nine_distinct_tools`
        and `test_mcp_entry_point_serves_the_phase_six_server`. Both are renamed; re-running (b) with
        function names normalised must show those two files identical in every other respect.
      * two *descriptive string literals*, which a docstring-only rule cannot reach but which must not
        keep a dead phase id: the `--run-eval` help text in `tests/conftest.py`, and the "How to read
        this" bullet in `tests/eval/test_rag.py`. The second one is load-bearing — that test
        **generates** `docs/eval_report.md`, so editing the committed report without editing its
        generator would be silently reverted by the next `make test-eval`. Both strings must end up
        byte-identical to what `docs/eval_report.md` now says.
      Any other name change, any other string literal, or any file failing (b), is a mistake. Land as
      one commit.

## 4. Re-target citations in build files and metadata

- [x] 4.1 Point the per-layer coverage comment in `Makefile` and the `fail_under` comment in
      `pyproject.toml` at `docs/coverage_report.md` instead of "ROADMAP 10.4"; re-point the eleven
      dependency comments in `pyproject.toml` that say a package "joins the runtime set in phase N" at
      the layer that introduced it; and drop the phase tags from the two section headers in
      `.env.example`. Verify: `make coverage-check` still passes and
      `git grep -nE 'ROADMAP|[Pp]hase' -- Makefile pyproject.toml .env.example` returns nothing.
- [x] 4.2 Reword the `ROADMAP 10.4` reference in the `[0.1.0]` entry of `CHANGELOG.md` to describe the
      floors without the dead id, and add an `[Unreleased]` entry for this change. The other phase
      numbers in `CHANGELOG.md` stay: they are release history (design D11), but none of them may name
      `ROADMAP.md` itself. Verify: the `[0.1.0]` section still describes the same facts,
      `grep -n ROADMAP CHANGELOG.md` returns nothing, and `[Unreleased]` is no longer empty.
- [x] 4.3 Verify the sweep across the tree with `git grep` (tracked files only, so the two virtualenvs
      and `__pycache__` cannot mask a result). Three checks:
      (a) the dead filename, `git grep -n 'ROADMAP' | grep -v '^openspec/'
      | grep -v '^CHANGELOG.md' | grep -v '^CONTRIBUTING.md' | grep -v '^ROADMAP.md'` returns
      nothing — `docs/adr/` included. (`ROADMAP.md` itself is excluded here because it is not deleted
      until 5.1 and naturally contains its own name; 8.1 drops that exclusion once it is gone.)
      (b) the vocabulary, `git grep -niE 'roadmap|[Pp]hase' | grep -v '^openspec/'
      | grep -v '^CHANGELOG.md' | grep -v '^CONTRIBUTING.md' | grep -v '^docs/adr/'
      | grep -v '^docs/ARCHITECTURE.md' | grep -v '^tests/eval/fixtures/news.jsonl'` returns nothing;
      (c) case-insensitivity matters — run (b) without `-i` and count the difference, so the
      `Roadmap 5.3` / `roadmap 3.8` casing is demonstrably covered rather than assumed.
      The two files outside the obvious set must be accounted for: `.env.example` is edited, and the
      `news.jsonl` fixture is exempt as article text. Land as one commit.

## 5. Delete the roadmap

- [x] 5.1 `git rm ROADMAP.md` and confirm nothing in the tree points at it. Verify: the file is gone,
      the group 4 sweep still returns nothing, and `make lint && make test` is green. Land as its own
      commit, with no other change in it.

## 6. Rewrite the README

- [x] 6.1 Rewrite the title block, badges, one-line description and the "key features" list, replacing
      the phase-by-phase status paragraph with a plain statement of what the project does today and
      what it is. Verify: the README mentions no phase and no roadmap, and the badge targets still
      resolve.
- [x] 6.2 Keep and tighten the quick starts: install, the CLI (with a `jq` example), and MCP, including
      the client setup that points at the committed `.cursor/mcp.json`. Verify: the commands shown
      match `make help` and `uv run numenews --help`, and every relative link resolves.
- [x] 6.3 Add a short "How OpenSpec is used here" section: where specs live, where changes live, the
      propose → apply → archive loop, and which capabilities are specified today. Verify: it names
      `mcp-surface` and `cli-surface` and links only to paths that exist.
- [x] 6.4 Keep the project-layout tree and command table current, and rewrite the documentation index
      so its roadmap entry is replaced by `openspec/`. Verify: every link in the index resolves and the
      list covers every file in `docs/`.
- [x] 6.5 Close with a short, informal contributing pointer and the license. Verify: the README has
      title, badges, description, features, quick start, OpenSpec usage, structure, contributing and
      license sections, in that order.

## 7. Contributing guide and GitHub templates

- [x] 7.1 Add an OpenSpec workflow section to `CONTRIBUTING.md` (propose → review → implement →
      archive), state that new work starts as a change and not as an edit, and say where the retired
      phase history now lives (`git log`, the `v0.1.0` tag, `CHANGELOG.md`). Verify: the section names
      the four steps and no longer implies a roadmap exists.
- [x] 7.2 Add `.github/PULL_REQUEST_TEMPLATE.md` asking for the change name, the `tasks.md` items
      completed and the verification commands run. Verify: the file exists and names `openspec/`.
- [x] 7.3 Add `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md` and
      `.github/ISSUE_TEMPLATE/config.yml`, routing feature requests to `/openspec-propose`. Verify: the
      two forms have front matter with a `name` and `about`, and `config.yml` parses as YAML.

## 8. Integration verification

- [x] 8.1 Confirm the three checks across the whole tree with `git grep` (tracked files only, so the
      virtualenvs and `__pycache__` cannot mask a result):
      (a) `git grep -n 'ROADMAP' | grep -v '^openspec/' | grep -v '^CHANGELOG.md'
      | grep -v '^CONTRIBUTING.md'` returns nothing — the dead filename is gone everywhere else,
      `docs/adr/` included;
      (b) `git grep -niE 'roadmap|[Pp]hase' | grep -v '^openspec/' | grep -v '^CHANGELOG.md'
      | grep -v '^CONTRIBUTING.md' | grep -v '^docs/adr/' | grep -v '^docs/ARCHITECTURE.md'
      | grep -v '^tests/eval/fixtures/news.jsonl'` returns nothing;
      (c) `git grep -niE 'roadmap|[Pp]hase' -- .github/ README.md AGENTS.md .env.example` returns
      nothing, which is the strictest bar because a newcomer reads those first.
      `CHANGELOG.md` and `CONTRIBUTING.md` are exempt in (a) and (b) on purpose: each carries a
      deliberate record that the file was deleted and where its history went, which design D1
      requires. Confirm those mentions are prose and not links — `git grep -n 'ROADMAP' --
      CHANGELOG.md CONTRIBUTING.md` must show no `](` on any line. The `docs/adr/`,
      `docs/ARCHITECTURE.md` and fixture exclusions in (b) are the phase-vocabulary-only surfaces of
      design D11; confirm each excluded file's remaining matches really are history, decision
      rationale or article data, and not a citation.
- [x] 8.2 Check every relative markdown link in the files this change touched resolves to an existing
      path, with a one-off script over the changed files. Verify: no unresolved target is reported.
- [x] 8.3 Run `make lint && make test && make coverage-check` and confirm all three are green with the
      per-layer floors unmoved and the test count unchanged from before the change.
- [x] 8.4 Archive the change so the two spec deltas land in `openspec/specs/`. Verify:
      `openspec/specs/mcp-surface/spec.md` and `openspec/specs/cli-surface/spec.md` exist with a
      `## Purpose`, `openspec list` shows no active change, and `openspec list --specs` shows both
      capabilities.
