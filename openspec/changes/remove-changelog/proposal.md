# Proposal

## Why

`CHANGELOG.md` is the last artifact of the roadmap era that still claims to be the record of what
shipped. That job belongs to OpenSpec now: `openspec/specs/` holds the behaviour that ships and
`openspec/changes/archive/` holds what each change did. The changelog duplicates both, and its
`[Unreleased]` section has become a second place to describe work the specs already describe.

It is also already failing at the job. `[Unreleased]` was last written while the previous change was
still in flight; two commits have landed since — tracking the agent skills and adapting the commit
skill — and neither is recorded. A record that nobody updates is worse than no record, because it
reads as current.

## What Changes

- Delete `CHANGELOG.md` outright. No archived copy is kept, matching the `ROADMAP.md` removal: the
  build history survives in `git log` and in the `v0.1.0` tag.
- Remove the "update `CHANGELOG.md` under `[Unreleased]`" step from every document that carries it —
  `CONTRIBUTING.md`'s workflow and the four `docs/agentic/` documents — including its appearance as a
  Definition-of-Done item in `EVAL_OF_AGENT.md`.
- Re-anchor `CONTRIBUTING.md`'s "Where the old roadmap went", which currently names the changelog as
  the record of what each phase shipped. It will name `git log`, the `v0.1.0` tag and the archived
  change instead.
- Leave the archived `adopt-openspec-workflow` artifacts alone. They are frozen history; only the
  live documents are re-anchored.
- Record the resulting rule in `CONTRIBUTING.md` so the next contributor knows release notes are not
  expected anywhere: a release is a tag, and its content is `git log`.

`pyproject.toml`'s `version` stays the authoritative version and `v0.1.0` stays the only tag.
Semantic versioning keeps applying to those; what disappears is a file that restated it.

## Capabilities

### New Capabilities

None. This change removes a document and edits contributor guidance. It introduces no capability
whose behaviour could be observed from outside the repository.

### Modified Capabilities

None. `mcp-surface` and `cli-surface` describe the nine MCP tools and the six CLI commands; this
change touches neither. `.openspec.yaml` sets `skip_specs: true` for that reason — no requirement is
invented to satisfy validation.

## Impact

- **Deleted**: `CHANGELOG.md` (242 lines: `[Unreleased]`, `[0.1.0]` and `[0.0.0]`).
- **Edited**: `CONTRIBUTING.md`; `docs/agentic/AGENT_WORKFLOW.md`, `EVAL_OF_AGENT.md`,
  `PROMPTING_PLAYBOOK.md`, `TOOLING.md` — 8 references across 5 files.
- **Unchanged**: both capabilities, all of `src/` and `tests/`, `pyproject.toml`, `Makefile`.
- **No tooling depends on it**: `pyproject.toml` has no `Changelog` URL under `[project.urls]`, and
  `README.md` carries no version or release badge. Removal breaks nothing that reads it.
- **Phase vocabulary** loses one of its three sanctioned live homes. `docs/adr/`, the
  `docs/ARCHITECTURE.md` "How it was built" narrative and the eval fixture keep theirs.
