# Implementation Plan: A refusal notice that names a repair the operator can actually perform

**Branch**: `tracked-meta-unanswerable-git-01M6GRFF` | **Date**: 2026-11-03 | **Spec**: `kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/spec.md`
**Input**: Mission specification from `kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/spec.md`

## Summary

`read_tracked_meta` already knows *why* it could not answer — it failed to identify the repository,
failed to read HEAD's blob, or was refused on ownership grounds — but it throws that information
away and returns a bare `TrackedMeta(None, unavailable=True)`. The shared notice then has one
fallback sentence: "tracked meta.json is missing from the working tree and git could not produce its
content … restore it with `git checkout -- <path>`". That sentence asserts something git never
established (the path is tracked) and prescribes a command that fails for the same reason the
classification did.

The change is diagnosis only. `TrackedMeta` gains one optional *unreadable cause*
(`"repository" | "ownership" | "objects"`), `read_tracked_meta` sets it on the two branches where
git could not answer, and `tracked_meta_notice` renders one cause-specific tail that names the repair
class and explicitly says a file restore cannot succeed yet. Nothing about the refusal changes: same
`refuse=True`, same `TRACKED_META_UNAVAILABLE` code, no write on any path, and the healthy
restore-or-rebuild notices are untouched.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor), `from __future__ import annotations`
**Primary Dependencies**: stdlib only on the touched paths (`subprocess` via `kernel.git.runner`); pytest for tests
**Storage**: `meta.json` files and a git checkout; no database
**Testing**: `pytest` (module is `pytest.mark.unit` + `pytest.mark.git_repo`, real `git init` fixtures); `ruff check`, `ruff format --check`, `mypy`
**Target Platform**: Linux/macOS developer hosts running `spec-kitty upgrade`
**Project Type**: single Python package (`src/specify_cli`, `src/kernel`, `src/charter`)
**Performance Goals**: classification stays one-to-three git invocations per Mission (unchanged); the cause is data, not another probe
**Constraints**: the notice must stay one line, project-relative, under the operator's reading budget; no stderr echo
**Scale/Scope**: two product modules plus one shared predicate relocation; three new tests and one strengthened test in a single existing suite

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the notice text stays in `tracked_meta_notice` (it is already the one
  owner for this refusal); the "git refused on ownership" predicate gets **one** owner instead of a
  second copy (C-005): it moves from the private `_is_dubious_ownership` in `core/git_preflight.py`
  into `kernel.git.runner` beside `GitCommandError`, and both call sites import it.
  `git_preflight`'s behaviour and its tests are unchanged.
- **ATDD-first** — the red proof is written through the pre-existing entry points
  (`classify_missing_tracked_meta` / `read_tracked_meta`), not through a new helper.
- **Campsite cleaning** — the touched notice function is already small and flat; the per-cause text is
  hoisted into module constants (keeps every function well under the complexity ceiling) rather than
  growing a nested conditional.
- **Locality of change / smallest viable diff** — no consumer signature changes: `MissingTrackedMeta`
  keeps its shape and every seam keeps rendering `.notice`.
- **Test remediation discipline** — no existing assertion is relaxed; the new coverage is added
  beside the existing refusal pins, and the healthy-path tests act as the positive control.
- **No ownership-policy weakening** (C-003) — the mission reads git's refusal, never changes git's
  config, and the ownership notice names trust as an operator decision scoped to one checkout.
- **Terminology** — Mission, not Feature; "primary"/"merge"/"routing" do not appear in the diff's new prose.

## Project Structure

### Documentation (this mission)

```
kitty-specs/tracked-meta-unanswerable-git-01M6GRFF/
├── plan.md              # this file
├── spec.md              # mission specification
├── tasks.md             # work packages
└── traces/              # approach / design-decisions / tooling-friction
```

### Source Code (repository root)

```
src/kernel/git/runner.py                     # + refuses_ownership(): the single stderr classifier
src/kernel/git/__init__.py                   # + re-export
src/specify_cli/core/git_preflight.py        # uses the shared predicate (its private copy goes)
src/specify_cli/mission_metadata.py          # TrackedMeta.unreadable_reason + the two call sites
src/specify_cli/upgrade/tracked_meta_notice.py  # one cause-specific tail per unreadable cause

tests/specify_cli/upgrade/test_read_tracked_meta_6673.py   # red-first coverage (strengthened + new)
docs/changelog/unreleased/<pr>.fixed.md                    # per-PR fragment
```

**Structure Decision**: single-package layout, following the existing mirror (`src/specify_cli/x.py` →
`tests/specify_cli/...`). `tests/specify_cli/upgrade` is an out-of-matrix directory (nightly only), so
the module's evidence is a targeted local run recorded in the PR, not a matrix job.

## Implementation Concern Map

### IC-01 — Carry the cause on the classifier's answer

- **Purpose**: turn "git could not answer" from a single `unavailable` boolean into a value that says which of the three answers git failed to give.
- **Relevant requirements**: FR-001, FR-002, C-001, C-004, NFR-002
- **Affected surfaces**: `src/specify_cli/mission_metadata.py` (`TrackedMeta`, `read_tracked_meta`, `_GitRefuses`, a small `_unreadable_reason` classifier)
- **Sequencing/depends-on**: none
- **Risks**: the field must be set *only* together with `unavailable=True`; `_index_tracks_meta`'s
  fail-closed `index_only` path already sits behind a successful prefix read and must not be
  re-classified. A timeout keeps raising.

### IC-02 — One owner for the ownership refusal

- **Purpose**: reuse the existing "git refused on ownership" predicate instead of writing a second copy in the metadata module.
- **Relevant requirements**: C-005, FR-005
- **Affected surfaces**: `src/kernel/git/runner.py`, `src/kernel/git/__init__.py`, `src/specify_cli/core/git_preflight.py`
- **Sequencing/depends-on**: none (IC-01 imports it, so it lands first)
- **Risks**: `git_preflight` must keep its exact issue codes and remediation text; its tests are the guard.

### IC-03 — Render the cause as a repair class

- **Purpose**: give each cause a tail that names what actually repairs it, states that tracked-ness is unknown, and never offers `git checkout --`.
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, C-002, C-003, NFR-001, NFR-004
- **Affected surfaces**: `src/specify_cli/upgrade/tracked_meta_notice.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the `tracked_meta_refusal` lead ("has lost its mission_id") shares the tail; the wording
  must read correctly with the file present. The word "tracked" is dropped only for the unverified
  subject.

## Complexity Tracking

No charter violations. Each touched function stays well inside `max-complexity = 15`; the added
branch is one `if` plus a constant lookup.
