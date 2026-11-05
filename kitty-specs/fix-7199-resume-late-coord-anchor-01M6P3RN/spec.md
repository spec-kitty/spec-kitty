# Mission Specification: A resume that lands a late coordination commit finishes teardown

**Mission Branch**: `issue-7199-resume-late-coord-anchor`
**Created**: 2026-11-05
**Status**: Draft
**Input**: Issue #7199 — `consolidate --resume`: a coordination commit after the resume's own capture is refused although its window landed it.

## Problem

`spec-kit consolidate` ends by deleting the Mission's coordination branch
(`kitty/mission-<slug>`) at the tip the projection teardown gate approved
(`src/specify_cli/consolidation/phase_teardown.py`). Before the branch goes,
`_land_late_coordination_commits` re-projects the window that landed after the merge
captured its coordination tip, commits it on the target, and proves every coordination
record in it byte-identical there (`assert_late_window_landed`, #5570 / #6791 / #6857).

PR #7124 (#6871) gave the FIRST run that window and, after the proof, advanced the approved
tip (`run.coord_tip_after_projection`) to the proven one — but only on a first run
(`if not run.is_resume`). A `--resume` keeps the anchor its own claim or bookkeeping phase
captured. When a coordination commit lands on the branch **after** that capture — a
concurrent `agent issue-verdict`, a status emit from another checkout — the resume's own
window (base `state.pre_mutation_coord_sha`) lands and proves it, and then the projection
teardown gate refuses with `the coordination tip moved since projection captured its window
(compare-and-swap failed)`, even though the content is already on the target. The refusal
fails closed (branch, worktree and marker kept), so nothing is lost; the operator just has
to run `--resume` a second time for a landing that was already complete.

## Goal

A resume that proves it landed the late window advances the tip teardown approves, exactly
as a first run does, so it finishes instead of refusing work it just completed. The proof
itself, the refusal kinds and every fail-closed leg stay unchanged.

## User Scenarios & Testing

### User Story 1 - A resume finishes after landing a late coordination commit (Priority: P1)

An operator follows a refusal's own instruction and commits on the coordination branch, or a
concurrent writer emits a verdict, *after* the resume has already captured the coordination
tip. The resume's late window carries that commit, lands it on the target and proves it.
The consolidation completes: the branch is deleted at the proven tip, the marker is
flattened, and the record is on the target. No second `--resume` is needed.

**Why this priority**: this is the reported defect. It costs an operator a full extra
consolidation round on a landing that is already complete, and the refusal text claims the
content may have been lost when it was not.

**Independent Test**: `uv run pytest tests/coordination/test_projection_teardown.py -q -k resume`
— the new resume case fails at the base commit (the gate refuses, `compare-and-swap failed`)
and passes after the change.

**Acceptance Scenarios**:

1. **Given** a resume whose recorded coordination anchor predates a coordination commit that
   the late window lands and proves, **When** the teardown runs, **Then** the approved tip
   moves to the proven tip, the projection teardown gate passes, and the branch is deleted.
2. **Given** the same fixture, **When** the teardown completes, **Then** the late record is
   committed on the target branch and `run.coord_tip_after_projection` equals the tip the
   assertion covered.
3. **Given** a commit that lands *while* the projection runs (the live ref no longer equals
   the tip the assertion covered), **When** the teardown runs, **Then** the anchor does not
   move and the gate still refuses fail-closed with the branch kept.

### User Story 2 - A resume with nothing late is unchanged (Priority: P2)

A resume whose coordination branch is where its anchor says it is builds an empty window,
projects nothing, approves nothing new, and makes no extra commit. A resume that cannot build
its window (no recorded checkpoint or pre-mutation tip) still refuses fail-closed, and a
resume whose ref cannot be read still refuses rather than skipping the window.

**Why this priority**: the change must be provably additive; the existing resume guarantees
are the reason `--resume` is trusted to finish an interrupted consolidation.

**Independent Test**: `uv run pytest tests/coordination/test_projection_teardown.py
tests/consolidation/test_late_teardown_projection.py -q` — the existing resume cases
(`test_resume_with_nothing_landed_late_commits_nothing`,
`test_resume_with_an_unreadable_window_refuses_and_keeps_the_branch`,
`test_resume_refuses_a_window_that_deletes_a_checkpoint_present_record`,
`test_resume_projects_a_verdict_recorded_after_the_teardown_refusal`) stay green untouched in
their assertions.

**Acceptance Scenarios**:

1. **Given** a resume with `pre_mutation_coord_sha == live tip`, **When** the teardown runs,
   **Then** the target gains no commit and the approved tip does not change.
2. **Given** a resume whose window deletes a record the target holds, **When** the teardown
   runs, **Then** it refuses with `COORD_LATE_PROJECTION_REFUSED`, keeps the triple, and names
   the per-kind repair.

### Edge Cases

- **Resume that short-circuits the bookkeeping phase** (`_resume_reconciliation_already_passed`):
  it never captures `coord_tip_after_projection`, so the gate falls back to the claim-time
  checkpoint. If its window lands a later commit, the anchor must advance from "no capture" to
  the proven tip; the gate must not compare against the older checkpoint.
- **A commit that lands during the projection**: the ref no longer equals the tip read for the
  window, so the advance does not happen and the gate refuses (unchanged, fail-closed).
- **An unreadable coordination ref** (git exits non-zero): refuse, keep the branch (unchanged).
- **An absent coordination branch** (git exits 1): quiet no-op, no window (unchanged).
- **A resume with no recorded window base**: `_refuse_unbuildable_late_window` still refuses.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | A proven resume window advances the approved tip | As an operator, I want a resume that landed its late window to finish teardown so that a complete landing is never refused. | High | Open | [build] | no — at the base commit the gate refuses and the branch survives; the test asserts completion on the same fixture. |
| FR-002 | The advance stays a compare-and-swap on the proven tip | As a maintainer, I want the anchor to move only when the live ref still equals the tip the assertion covered so that a foreign commit is never stamped approved. | High | Open | [ratchet] | no — a same-fixture case injects a commit during the projection and asserts the gate still refuses with the anchor unmoved. |
| FR-003 | A resume with nothing late stays a no-op | As an operator, I want a clean resume to make no extra commit and approve no new tip. | Medium | Open | [ratchet] | no — asserts the target ref and the anchor are byte-identical before/after on the same fixture. |
| FR-004 | The unbuildable and unreadable window refusals are unchanged | As a maintainer, I want the fail-closed legs preserved so that teardown never deletes a branch it could not read. | Medium | Open | [ratchet] | no — the existing refusal cases stay green and are named in the WP. |
| FR-005 | The operator-facing wording matches both run kinds | As an operator, I want the guide and the code comments to describe the approved tip as "the tip whose records the assertion proved", on either run kind. | Low | Open | [build] | no — the guide currently frames the anchor advance as a first-run step; the diff corrects it. |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new surface | No new CLI flag, configuration key, exit code or error code; the diff is confined to one phase module, its docstrings, tests and docs. | Maintainability | High | Open |
| NFR-002 | Targeted tests stay fast | The touched test files run in under 15 minutes with `-n 4 -p no:randomly` on this host. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the #7124 machinery | Extend the existing anchor advance, window base and assertion; do not add a second window selector, a second refusal text or a resume-only branch. | Technical | High | Open |
| C-002 | No weakening of a gate | `assert_late_window_landed`, the projection teardown gate, the branch-delete compare-and-swap, `_refuse_unbuildable_late_window` and the unreadable-ref refusal keep their behaviour. | Technical | High | Open |
| C-003 | Smallest viable diff | Change the minimum number of lines; no refactor of the teardown or the projection seam. | Technical | Medium | Open |

### Key Entities

- **Approved coordination tip** (`run.coord_tip_after_projection`): the tip the projection
  teardown gate and the branch-delete compare-and-swap anchor on. Captured by the claim or
  bookkeeping phase; may be advanced by teardown to a tip the post-projection assertion proved.
- **Late window**: `base..coordination tip`, where `base` is

  `state.pre_mutation_coord_sha` on a resume and the captured tip on a first run.
- **Proven tip**: the coordination tip the window assertion covered, and the ref still equals
  when teardown advances.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A resume whose late window lands and proves a post-capture coordination commit completes teardown with exit 0 and no branch left behind, where the base commit exits 1. — [build] · no-op passable: no
- **SC-002**: Every existing resume-refusal and first-run test in the touched files passes unchanged (0 assertions edited to pass). — [ratchet] · no-op passable: no
- **SC-003**: `run.coord_tip_after_projection` equals the projected tip after a proven resume landing, and is unchanged when the ref moves during the projection. — [ratchet] · no-op passable: no
