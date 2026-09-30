# Proposal

## Why

`ROADMAP.md` has finished its job. All eleven phases are closed — 359 ticked tasks, zero open, in
progress or cancelled — and the tag `v0.1.0` sits on the last of them. What remains in those 142 KB
is a *history* of how the project was built, wrapped around a phase list that cannot accept new work
without pretending it is unfinished old work.

OpenSpec is initialized in the same repository and is completely empty, so the project currently
makes two contradictory claims about where truth lives: `AGENTS.md` (and six `docs/agentic/` files,
and twelve ADRs) still say `ROADMAP.md` is the single source of truth, while `openspec/` is the tool
that is actually going to receive the next feature. Resolving that in favour of OpenSpec — and
retiring the roadmap out loud — is what makes the next change a real propose → review → implement →
archive loop instead of an archaeology exercise.

## What Changes

- **BREAKING**: delete `ROADMAP.md`. It is not archived, not renamed and not moved — the history it
  holds already lives in `git log`, in the `v0.1.0` tag and in `CHANGELOG.md`, and a frozen copy in
  `docs/` would keep the "which file is authoritative?" question alive.
- **Backfill the external contracts into OpenSpec**: two new capabilities, `mcp-surface` and
  `cli-surface`, describing the behaviour v0.1.0 already ships. These are the two interfaces an
  outside user depends on; the internals stay undocumented in OpenSpec until a real change touches
  them.
- **Rewrite every citation of the roadmap** — ~11 markdown links, ~145 prose mentions that name the
  file, and ~131 more lines that mention a phase (`(phase 8.3)`, `> Phase 3.`, or a bare "the phase
  that needs it") without ever writing `ROADMAP`. 276 lines across 108 files in `docs/`, tests, `src/`
  docstrings, `Makefile` and `pyproject.toml`, so that each points at the document or spec that now
  owns the claim. No dangling reference to a deleted file or to a numbering scheme that no longer
  exists. Three surfaces keep their phase vocabulary on purpose because there the number is a
  historical record rather than a pointer: `CHANGELOG.md`, `docs/adr/`, and the "How it was built"
  narrative in `docs/ARCHITECTURE.md`.
- **Rewrite `AGENTS.md`** to name OpenSpec as the source of truth for what is built and what is next,
  and to describe the change workflow in place of the roadmap rules.
- **Rewrite `docs/agentic/`** (6 files, 28 references). The workflow they describe is built on
  roadmap task ids and phase gates; it becomes OpenSpec change ids, `tasks.md` checkboxes and the
  archive step.
- **Modernize repository presentation**: a rewritten `README.md` (badges, features, quick start for
  both interfaces, an "how OpenSpec is used here" section, structure, contributing, license), an
  OpenSpec workflow section in `CONTRIBUTING.md`, and minimal `.github/` issue and PR templates that
  point at OpenSpec.
- **Re-anchor the coverage floors** currently cited as "ROADMAP 10.4" to `docs/coverage_report.md`,
  which is where the numbers and the command already are.
- **Skip** `CODE_OF_CONDUCT.md` and `SECURITY.md`. No community to moderate, no hosted service, no
  user data at rest; the only secret is the author's own API key in a gitignored `.env`, which
  `.env.example` and `.gitignore` already handle. Adding either would be exactly the ceremony this
  project avoids. Revisit if the repository starts taking outside contributions.

## Capabilities

### New Capabilities

- `mcp-surface`: the nine MCP tools — their inputs, return shapes, the context-free subset, the
  caching behaviour of `build_forecast`, and how an expected failure is reported to a client. This is
  the contract `docs/MCP_TOOLS.md` documents narratively.
- `cli-surface`: the six one-shot CLI commands — the JSON-only stdout contract, the `--date` grammar,
  the exit codes, and the "state lives in Qdrant, not in process memory" idempotency guarantee. This
  is the contract `docs/USER_FLOW.md` documents narratively.

### Modified Capabilities

None. `openspec/specs/` is empty, so both capabilities above are additions from OpenSpec's point of
view even though the code they describe already exists.

## Impact

- **Deleted**: `ROADMAP.md` (root).
- **Added**: `openspec/specs/mcp-surface/spec.md`, `openspec/specs/cli-surface/spec.md`,
  `.github/` templates (issue config, bug/feature forms, PR template).
- **Heavily edited**: `README.md`, `CONTRIBUTING.md`, `AGENTS.md`, all six `docs/agentic/` files,
  `docs/coverage_report.md`, `Makefile`, `pyproject.toml`, `CHANGELOG.md`.
- **Link-target edits**: `docs/` headers (31 files, incl. 12 ADRs), `tests/` docstrings (68 files),
  `src/` docstrings (~40 files), plus the phase comments in `pyproject.toml` and `Makefile`.
- **Untouched**: all product behaviour. No module, prompt, model, collection or command changes, and
  no dependency changes. `make lint && make test` must stay green, with the coverage floors unmoved.
- **Retained**: `.cursor/mcp.json` is committed and tracked, and the client-setup links that point at
  it (`README.md`, `docs/FAQ.md`, `docs/MCP_TOOLS.md`, `docs/agentic/TOOLING.md`) stay valid. An
  earlier draft of this change recorded the file as deleted and planned to drop those links; it was
  restored, so the links are kept and only checked.
