# Design

## Context

See `proposal.md` — Why. Three properties of the current tree shape the approach:

1. **`CHANGELOG.md` is a live reference, not just a document.** Eight references across five files:
   one (`CONTRIBUTING.md:33`) states where the old roadmap history went, and the other seven
   instruct contributors to update the file — `CONTRIBUTING.md`'s pull-request step 3, and the four
   `docs/agentic/` documents, including a Definition-of-Done item. Deleting the file without editing
   those leaves five documents telling the reader to update something that does not exist.
2. **One of those references is a markdown link** — `CONTRIBUTING.md:33` links `CHANGELOG.md`. The
   others are inline code. So the edit order matters if every commit is to leave the tree consistent.
3. **The archived change names the changelog as an owner.** Its design maps roadmap phase 10 to
   `docs/coverage_report.md` and `CHANGELOG.md`, and its D11 lists `CHANGELOG.md` as one of three
   surfaces allowed to keep phase vocabulary. Archived artifacts are frozen, so this change does not
   touch them; it re-derives the live consequences instead.

## Goals / Non-Goals

**Goals:**

- No document in the tree tells a contributor to maintain a changelog.
- Each commit leaves the tree self-consistent: no intermediate state has a link to a deleted file.
- A contributor who wonders where release notes went finds the answer stated, not implied.

**Non-Goals:**

- Restoring release notes in any form — annotated tag messages, GitHub Releases, a `docs/` history
  page. The record is `git log` and the `v0.1.0` tag. Wanting notes later is a new change.
- Rewriting the archived `adopt-openspec-workflow` artifacts. They are history and still read true for
  the moment they describe.
- Any change to `src/`, `tests/`, dependencies, or the two capabilities.

## Decisions

### D1 — Delete, with the tag and `git log` as the record

**Chosen:** `CHANGELOG.md` is deleted. Nothing replaces it as a file.

**Alternatives considered:** moving release notes into annotated tag messages and documenting
`git tag -a`; putting them on GitHub Releases; keeping the file but freezing it at `[0.1.0]`.

**Why:** every alternative reintroduces the thing this change removes — a second, hand-maintained
description of work that `openspec/specs/` and `openspec/changes/archive/` already describe. The
annotated-tag option is the most tempting, but it fails for the same reason the file did: notes are
written by hand at release time and drift the moment someone forgets, which is exactly what happened
here. `git log` cannot drift. The `v0.1.0` tag marks the release, and `pyproject.toml`'s `version`
stays the authoritative version number.

**The release history is not lost.** `git show v0.1.0:CHANGELOG.md` recovers the `[0.1.0]` and
`[0.0.0]` entries for as long as the tag exists — which is what makes outright deletion safe rather
than destructive. Only the `[Unreleased]` text is unique to the working tree, and it is already
superseded by the archived change it describes.

### D2 — Remove the step; do not replace it

The "update `CHANGELOG.md` under `[Unreleased]`" instruction is deleted from all five documents. No
substitute step is introduced.

**Why:** the step exists to keep a file current. With no file there is no step, and inventing a
replacement would recreate the drift in a new form. The per-change record already exists — it is the
change's proposal and spec delta, archived under `openspec/changes/archive/`.

### D3 — State the rule where a contributor will look

`CONTRIBUTING.md` gains a short `## Releases` section: a release is a tag, its content is `git log`,
there is deliberately no changelog, and the pre-0.2 history is available at
`git show v0.1.0:CHANGELOG.md`. The section that currently says the changelog "records what each
phase shipped" is re-anchored to `git log`, the `v0.1.0` tag and the archived change.

The new section replaces pull-request step 3 ("Update `CHANGELOG.md` under `[Unreleased]` if
user-facing"), which is deleted and the remaining steps renumbered. `CONTRIBUTING.md` has no
versioning or release material today, so the note creates its home rather than joining one.

**Why:** an unstated removal is discovered as an absence and gets "fixed" by recreating the file. One
sentence prevents that, and the same sentence keeps D1's reasoning reachable without an ADR — this is
a documentation convention, not an architectural decision.

### D4 — Re-anchor the live documents, leave the archive alone

Only files outside `openspec/changes/archive/` are edited. The archived design's phase-10 mapping and
its D11 exemption list keep naming `CHANGELOG.md`.

**Why:** the archive records what was decided at the time, and at that time the changelog was the
owner and did carry phase vocabulary. Editing it would falsify the record. The live consequence is
narrow: phase numbers lose one of their three sanctioned homes (`docs/adr/`, the `docs/ARCHITECTURE.md`
"How it was built" narrative and the eval fixture keep theirs), and no sweep is needed — deleting the
file removes its phase vocabulary with it.

## Risks / Trade-offs

- **A stale instruction survives in one of the five documents** → verification greps tracked files for
  `changelog` and requires the only remaining hits to be inside `openspec/changes/archive/`.
- **The changelog is recreated later** → D3 states the rule in `CONTRIBUTING.md`; D1 records that
  wanting notes back is a new change, not a restore.
- **Someone needs the old release history** → `git show v0.1.0:CHANGELOG.md`; the tag is the anchor,
  and `CONTRIBUTING.md` names it.
- **An intermediate commit has a broken link** → the reference edits land first and the deletion
  lands alone, so no commit contains a link to a file that is already gone.
- **The removal breaks tooling** → none reads the file: no `Changelog` URL under `[project.urls]`, no
  version or release badge in `README.md`. Confirmed before proposing.
- **This change is mistaken for a product change** → both capabilities are untouched and
  `.openspec.yaml` sets `skip_specs: true`; the proposal says why rather than inventing a requirement.

## Migration Plan

Documentation and process only; nothing to deploy, and rollback is `git revert`. The order is: edit
the eight references across the five documents, then delete `CHANGELOG.md` in its own commit, so the
deletion is readable on its own and no intermediate state links to a missing file. No spec deltas
land at archive time, since none exist.
