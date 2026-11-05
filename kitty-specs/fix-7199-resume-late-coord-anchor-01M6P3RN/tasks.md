# Work Packages: A resume that lands a late coordination commit finishes teardown

**Inputs**: Design documents from `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/`
**Prerequisites**: `plan.md`, `spec.md`

**Tests**: Red-first. The resume case lands before the fix and must fail at the base commit with
the projection teardown gate's `compare-and-swap failed` refusal.

**Organization**: Two work packages. WP01 is the behaviour change and its regression evidence;
WP02 is the documented rule, the changelog fragment and the end-to-end resume proof.

## Path Conventions

- Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: The approved-tip advance on a resume (Priority: P0) 🎯 MVP

**Goal**: A resume whose late window lands and proves a coordination commit made after its own
capture advances `coord_tip_after_projection` to the proven tip, so the projection teardown gate
and the branch delete anchor on content that is on the target instead of refusing.
**Independent Test**: `uv run --frozen pytest tests/coordination/test_projection_teardown.py -q -p
no:randomly -k "resume or first_run or clean"` — the new resume cases fail at the base commit and
pass after the change; every existing case stays green.
**Prompt**: `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/tasks/WP01-resume-anchor-advance.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, C-001, C-002, C-003, SC-001, SC-003

### Included Subtasks

T001 Red: a resume whose late window lands a post-capture coordination commit completes
`_teardown_coordination_triple` instead of refusing (WP01)
T002 Red: the same fixture with a commit landing during the projection still refuses and leaves
the anchor unmoved (WP01)
T003 Drop the run-kind guard on the anchor advance and keep the compare-and-swap (WP01)
T004 Correct the docstrings and the field comment that describe the advance as first-run-only
(WP01)
T005 Re-run the existing resume, first-run, clean-run and refusal cases unchanged (WP01)

### Implementation Notes

- Reuse `_land_late_coordination_commits`, `assert_late_window_landed` and the existing
  `coord_tip_after_projection` field; do not add a selector, refusal or field.
- The advance is `projected_tip and live ref == projected_tip`; the `is_resume` condition is the
  only thing that goes.
- A resume that short-circuited the bookkeeping phase has `coord_tip_after_projection is None`
  and still must be able to advance — do not require a previous value.

### Parallel Opportunities

- T001 and T002 are independent test cases; T003 depends on neither to be written, only to pass.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Moving the anchor on a resume could stamp a foreign tip approved: the compare-and-swap and the
  T002 fail-closed case are the guard; neither may be relaxed.

---

## Work Package WP02: Documented rule, end-to-end proof, changelog (Priority: P1)

**Goal**: The recovery guide and the code prose describe the approved tip as "the tip whose
records the assertion proved" on either run kind; the real-CLI resume test still passes and is
strengthened where the change is observable; the changelog fragment exists in the fragment shape.
**Independent Test**: `uv run --frozen pytest
tests/consolidation/test_late_teardown_projection.py -q -p no:randomly -k resume` plus
`uv run --frozen python -m scripts.docs.check_changelog_style` (0 errors) and
`uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (errors=0).
**Prompt**: `kitty-specs/fix-7199-resume-late-coord-anchor-01M6P3RN/tasks/WP02-docs-and-proof.md`
**Requirement Refs**: FR-005, NFR-001, NFR-002, SC-002

### Included Subtasks

T006 Re-run the real-CLI resume control (`test_resume_projects_a_verdict_recorded_after_the_teardown_refusal`)
on the consolidated head and record the result; it cannot order the concurrency window the fix
addresses, so no duplicate assertion is added (see `traces/design-decisions.md` D3) (WP02)
T007 Update the recovery guide's first-run section so it states the approved tip advances on
either run kind once the window is proven (WP02)
T008 Add `docs/changelog/unreleased/<pr>.fixed.md` in the fragment shape (WP02)

### Implementation Notes

- `CHANGELOG.md` is assembled from fragments since #6988; never edit it.
- The guide's heading and closing paragraph are the only prose that frames the advance as a
  first-run step; the CLI reference already covers both run kinds.

### Parallel Opportunities

- T006, T007 and T008 are independent.

### Dependencies

- Depends on WP01 landing the behaviour the guide describes.

### Risks & Mitigations

- Claiming an end-to-end reproduction the real CLI cannot produce deterministically: the
  concurrency window is pinned in-process (WP01) and the guide is worded to describe the rule,
  not to promise a test shape.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: none needed; one module plus its tests and docs.
- **MVP Scope**: WP01 delivers the fix and its proof; WP02 is the operator surface.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP02 |
| NFR-001 | WP02 |
| NFR-002 | WP02 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP02 |
| SC-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Parallel? |
|------------|---------|--------------|-----------|
| T001 | Red: resume advances the proven tip and finishes | WP01 | Yes |
| T002 | Red: a commit during the projection still refuses | WP01 | Yes |
| T003 | Drop the run-kind guard, keep the CAS | WP01 | No |
| T004 | Docstring and field-comment corrections | WP01 | No |
| T005 | Existing resume/first-run/refusal sweep | WP01 | No |
| T006 | Real-CLI resume control re-run and recorded | WP02 | Yes |
| T007 | Recovery guide wording | WP02 | Yes |
| T008 | Changelog fragment | WP02 | Yes |
