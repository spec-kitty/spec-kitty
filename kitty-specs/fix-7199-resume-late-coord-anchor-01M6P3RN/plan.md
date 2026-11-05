# Implementation Plan: A resume that lands a late coordination commit finishes teardown

**Branch**: `issue-7199-resume-late-coord-anchor` | **Date**: 2026-11-05 | **Spec**: `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/spec.md`
**Input**: Mission specification from `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/spec.md`

## Summary

`_land_late_coordination_commits` already builds a window for both run kinds and proves it
landed before the coordination branch is deleted. PR #7124 (#6871) added the last step of
that sequence for a first run only: after the proof, record the proven tip as
`run.coord_tip_after_projection`, the value the projection teardown gate and the branch-delete
compare-and-swap anchor on. A `--resume` skips that step, so the gate compares against the
anchor its claim/bookkeeping phase captured earlier and refuses a commit its own window just
landed. The fix drops the run-kind guard: a resume window starts at the persisted pre-mutation
snapshot, which is at or before the captured anchor, so the same compare-and-swap advance is at
least as well-founded there as on a first run. One line of behaviour plus the docstrings,
comments, tests and the recovery guide that describe it.

## Technical Context

**Language/Version**: Python 3.11 (the repository's pinned interpreter)
**Primary Dependencies**: `typer`, `rich`, `git` CLI through `specify_cli.core.git_ops`
**Storage**: git refs (coordination branch, target branch) and
`.kittify/consolidation/<mission>/state.json`
**Testing**: pytest (`tests/coordination`, `tests/consolidation`, `tests/terminus`), real git
repositories built by fixtures, real CLI via `run_terminus`
**Target Platform**: developer workstation / CI Linux and macOS
**Project Type**: single project (`src/specify_cli`, mirrored `tests/`)
**Performance Goals**: unchanged; teardown does one extra ref read only on the advance check
that a first run already performs
**Constraints**: no new CLI flag, config key, exit code or error code; no change to the
assertion, the gate or the refusals
**Scale/Scope**: one function in one module (`phase_teardown.py`), its field comment in
`run_state.py`, two test modules, one recovery guide page, one changelog fragment

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the fix reuses `_land_late_coordination_commits`,
  `assert_late_window_landed` and the existing `coord_tip_after_projection` field. No second
  window selector, no second refusal, no new field. PASS.
- **ATDD-first / red-first** — the resume case is written first and must fail at the base
  commit with the gate's `compare-and-swap failed` refusal. PASS (proved in the WP).
- **Locality of Change / smallest viable diff** — one condition, plus the comments that would
  otherwise state the old rule. PASS.
- **No output-format contract change** — no CLI surface, wording of a refusal, exit code or
  error code changes. The only prose that changes is documentation of the anchor. PASS.
- **Test policy** — touched test files plus the owning subsystem directory of the changed
  module (`tests/coordination`, `tests/consolidation`, `tests/terminus`), not a full suite. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/
├── spec.md
├── plan.md              # This file
├── tasks.md
├── lanes.json
├── tasks/               # WP prompts
└── traces/              # approach / design decisions / tooling friction
```

### Source Code (repository root)

```
src/specify_cli/consolidation/
├── phase_teardown.py        # the anchor advance + the docstrings/comments that describe it
└── run_state.py             # the coord_tip_after_projection field comment

tests/coordination/
└── test_projection_teardown.py   # red-first resume case + fail-closed twin (the #7124 file)

tests/consolidation/
└── test_late_teardown_projection.py   # the real-CLI resume case, strengthened

docs/guides/how-to/recovery/recover-from-interrupted-merge.md
docs/changelog/unreleased/<pr>.fixed.md
```

**Structure Decision**: single project. The behaviour lives in the consolidation phase
module; the regression tests live where the #7124 first-run twins live, plus the real-CLI
resume test the issue names.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — The approved-tip advance covers both run kinds

- **Purpose**: Let a resume that proved its late window move the approved tip to the proven
  one, so the projection teardown gate and the branch delete anchor on content that is on the
  target instead of refusing work the run just landed.
- **Relevant requirements**: FR-001, FR-002, FR-003, C-001, C-002, C-003, SC-001, SC-003
- **Affected surfaces**: `src/specify_cli/consolidation/phase_teardown.py`
  (`_land_late_coordination_commits`, `_late_window_base` docstring),
  `src/specify_cli/consolidation/run_state.py` (field comment),
  `tests/coordination/test_projection_teardown.py`
- **Sequencing/depends-on**: none
- **Risks**: the compare-and-swap must stay a compare-and-swap — the advance may only happen
  when the live ref still equals the tip read for the window, else the gate must refuse.
  A resume that never captured an anchor (short-circuited bookkeeping) must be able to advance
  from the claim-time checkpoint value; the code must not require a non-`None` previous value.

### IC-02 — The documented rule and the regression evidence follow

- **Purpose**: Make the docs, the field comment and the refusal-adjacent prose describe the
  anchor as "the tip whose records the assertion proved" on either run kind, and pin the
  resume behaviour end to end with the real CLI.
- **Relevant requirements**: FR-004, FR-005, NFR-001, NFR-002, SC-002
- **Affected surfaces**: `docs/guides/how-to/recovery/recover-from-interrupted-merge.md`,
  `tests/consolidation/test_late_teardown_projection.py`,
  `docs/changelog/unreleased/<pr>.fixed.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: `check_changelog_style` rejects the pre-#6988 `[Unreleased]` entry shape; the
  fragment is a separate file, `CHANGELOG.md` is never edited.
