# Work Packages: Keep a coordination commit that lands before a first-run teardown

**Inputs**: Design documents from `kitty-specs/fix-6871-first-run-late-coord-01M6G9JR/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: Red-first is the point of this Mission: the failing case lands before the fix.

**Organization**: Two work packages. WP01 is the red proof and the fix on the first-run path;
WP02 is the operator-facing surface (refusal wording, changelog, docs) and the regression sweep
that proves the `--resume` guarantee was not traded away.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: First-run late-coordination window (Priority: P0) 🎯 MVP

**Goal**: A coordination commit that lands after the merge captured `coord_tip_after_projection`
survives a first-run teardown — landed and proven, or refused loudly with the triple kept —
without weakening the `--resume` window or its post-projection assertion.
**Independent Test**: `uv run pytest tests/coordination/test_projection_teardown.py -q` — the new
first-run cases fail at the base commit and pass after the change; the clean-run positive control
and the existing CAS cases stay green.
**Prompt**: `/tasks/WP01-first-run-late-window.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008

### Included Subtasks

T001 Write the failing first-run case in `tests/coordination/test_projection_teardown.py`: land a
coordination commit after `coord_tip_after_projection`, run `_teardown_coordination_triple`, and
assert the record is on the target ref and the branch is gone (RED at base: the branch is deleted
and the record is nowhere on the target).
T002 Write the failing first-run refusal case: a late commit that deletes a record the target
holds must refuse, keep the branch/worktree/marker, and name `spec-kitty consolidate --resume`.
T003 Add `_late_window_base` in `src/specify_cli/consolidation/phase_teardown.py` (resume →
`state.pre_mutation_coord_sha`; first run → `coord_tip_after_projection`) and drop the
`is_resume` early return, keeping `_refuse_unbuildable_late_window` on the resume path only.
T004 Record the proven tip: after the projection and `assert_late_window_landed` succeed on a
first run, advance `coord_tip_after_projection` to the tip the assertion covered, compare-and-swap
against the ref (never a fresh read), so the projection teardown gate and the branch delete anchor
on a proven tip.
T005 Update the module and function docstrings for the two windows; keep the #5570 commit message
and only distinguish the windows in the console line.

### Implementation Notes

- Reuse the existing seams; do not add a second record selector or a second refusal text.
- `_teardown_coordination_triple` keeps its order: project → fold status → pre-teardown tip →
  gated coord worktree teardown → CAS delete → flatten.

### Parallel Opportunities

- T001/T002 (tests) run before T003–T005 (implementation); the two test cases are independent.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Anchoring the first-run window on `pre_mutation_coord_sha` would re-walk the merge and
  manufacture refusals; the base is deliberately `coord_tip_after_projection`.

---

## Work Package WP02: Operator surface and regression sweep (Priority: P1)

**Goal**: The refusal reads correctly for both windows, the changelog fragment exists, any doc
that claims a `--resume`-only guarantee is corrected, and the resume suite proves it was not
weakened.
**Independent Test**: `uv run pytest tests/consolidation/test_late_teardown_projection.py
tests/consolidation/test_teardown_refusal_resume.py tests/terminus/test_coord_teardown_cas_branch_delete.py -q`
passes with no test weakened, and `check_changelog_style` accepts the fragment.
**Prompt**: `/tasks/WP02-operator-surface.md`
**Requirement Refs**: FR-006, FR-007, FR-009

### Included Subtasks

T006 Verify the first-run refusal routes through `_late_projection_refusal` so each refusal kind
keeps its own remedy (#6791); add a test asserting the first-run refusal names the branch, the
target and `--resume`.
T007 Run the existing resume/projection/refusal suites unchanged; record the results in the PR.
T008 Add `docs/changelog/unreleased/<pr>.fixed.md` in the fragment style (bold impact-first lead,
`(#6871, #6857)` refs, before/after, under 1,200 characters).
T009 Correct any doc page that states the late-window protection is resume-only.

### Implementation Notes

- No new CLI flag, config key or exit code (FR-009); the fragment is the user-facing surface.

### Parallel Opportunities

- T006/T007 and T008/T009 are independent once WP01 lands.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Changelog shape drift: `check_changelog_style` rejects the pre-#6988 `[Unreleased]` entry shape;
  write the fragment, never edit `CHANGELOG.md`.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none needed; the Mission is one phase module plus its tests.
- **MVP Scope**: WP01 delivers the fix; WP02 is the operator surface the PR must carry.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| FR-008 | WP01 |
| FR-009 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red: first-run late commit is lost | WP01 | P0 | Yes |
| T002 | Red: first-run late deletion refuses | WP01 | P0 | Yes |
| T003 | Window base selection, drop the early return | WP01 | P0 | No |
| T004 | Advance the approved tip only under proof | WP01 | P0 | No |
| T005 | Docstrings for the two windows | WP01 | P0 | No |
| T006 | Refusal routing + first-run refusal test | WP02 | P1 | Yes |
| T007 | Resume/projection/refusal regression sweep | WP02 | P1 | Yes |
| T008 | Changelog fragment | WP02 | P1 | Yes |
| T009 | Docs correction | WP02 | P1 | Yes |
