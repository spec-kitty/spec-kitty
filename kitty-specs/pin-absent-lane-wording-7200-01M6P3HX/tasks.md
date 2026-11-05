# Work Packages: Pin the absent-lane wording in move-task's evidence refusal

**Inputs**: `kitty-specs/pin-absent-lane-wording-7200-01M6P3HX/` — spec.md, plan.md, research.md
**Prerequisites**: plan.md, spec.md, research.md

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Pin the absence sentence and prove the guard (Priority: P1)

**Goal**: Pin the shipped `the lane branch … does not exist in this checkout` sentence in the existing real-Git missing-lane-with-a-sibling test, prove the new assertion fails under the `is unavailable` mutation, and record the internal changelog fragment.
**Independent Test**: the focused test fails on the mutated production sentence and passes on the shipped source; the real-Git module still reports three passes.
**Prompt**: `tasks/WP01-pin-absence-sentence.md`
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003

### Included Subtasks

- T001 Add the absence-wording assertion to `test_a_missing_lane_with_a_sibling_names_conditional_restore`, keeping the existing conditional-restore and never-created assertions.
- T002 Prove red-first non-vacuity: mutate `local_fact` in `wp_evidence.py` to `is unavailable` only temporarily, observe the test fail at the new assertion, and restore the source with no committed production diff.
- T003 Add the per-PR internal changelog fragment and rename it to the PR number once the PR exists.
- T004 Run the focused real-Git module, scoped Ruff/format, and changelog style; record the results.

### Implementation Sketch

1. Read the shipped `absent_lane_window_cause` sibling branch and the target test; reuse the existing `_gate_repo` fixture.
2. Write the assertion first, then run the mutation proof against it.
3. Restore `wp_evidence.py`; confirm `git diff --stat` contains no production file.
4. Add the fragment, run the focused checks, and prepare the PR evidence table.

### Parallel Opportunities

- None meaningful: T001–T002 share one test and one temporary mutation; T003 and T004 are delivery steps after the test settles.

### Dependencies

- None

### Risks

- Pinning the sentence too loosely (for example asserting only "does not exist") would let a sibling-path wording swap pass; pin the full local-fact sentence for the lane branch.
- The mutation must be fully reverted; verify `git diff` before staging.
