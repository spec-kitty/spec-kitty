# Mission Specification: Pin the absent-lane wording in move-task's evidence refusal

**Mission Branch**: `kitty/mission-pin-absent-lane-wording-7200-01M6P3HX`
**Created**: 2026-11-05
**Status**: Draft
**Input**: GitHub issue [#7200](https://github.com/spec-kitty/spec-kitty/issues/7200) — "Test gap: move-task's 'lane branch does not exist' wording for a missing lane with a sibling is unpinned (FR-001, Mission 250)".

## Intent Summary (confirmed)

- **Primary actor**: a maintainer relying on the FR-001 distinction from Mission 250 (`lane-window-never-created-recovery`) between an *absent* lane branch and an *unreadable* one.
- **Trigger**: in `tests/git_ops/test_move_task_evidence_refusals.py::test_a_missing_lane_with_a_sibling_names_conditional_restore`, changing the shipped sentence `the lane branch X does not exist in this checkout` to `the lane branch X is unavailable` leaves the whole test green. Nothing pins the absence wording on that path.
- **Desired outcome**: that test asserts the shipped absence wording on the missing-lane-with-a-sibling path, and the assertion is proven to fail under the same mutation. Production behaviour is unchanged.
- **Boundary**: test-only change plus a per-PR internal changelog fragment. No production file, no refusal code, no recovery wording, and no other test's contract changes. The never-created shape (no code lane has a branch) and the unreadable shape keep their existing guards.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pin the absence sentence where a sibling lane exists (Priority: P1)

As a maintainer, I want the missing-lane-with-a-sibling refusal to fail its test when the word "exist" is softened to "unavailable", so that FR-001's absence-versus-unreadability distinction cannot regress silently.

**Why this priority**: it is the whole issue; without this assertion the shipped diagnostic is unpinned.

**Independent Test**: run `test_a_missing_lane_with_a_sibling_names_conditional_restore` on the shipped source (passes) and under the `does not exist` → `is unavailable` production mutation (fails at the new assertion), then restore the source and re-run the focused suite (passes).

**Acceptance Scenarios**:

1. **Given** a code lane branch that is absent while a sibling code lane branch exists, **When** `move-task`'s evidence gate refuses review, **Then** the message contains `the lane branch kitty/mission-fx-lane-b does not exist in this checkout`.
2. **Given** the same fixture and a production mutation that replaces that sentence with `is unavailable`, **When** the test runs, **Then** it fails on the absence assertion.
3. **Given** the restored shipped source, **When** the same test and the three-case real-Git module run, **Then** they pass.
4. **Given** the same refusal, **When** the message is inspected, **Then** the conditional-restore and never-created distinctions still hold: the lane-tip ref and "If it did exist" are present and the "no lane of this Mission has a branch here" claim is absent.

### Edge Cases

- The sibling branch exists but the target lane's ref is missing: this is the shape under test; absence is a local fact, not a history claim.
- The production mutation is applied only temporarily for the red proof and is fully reverted; the committed diff contains no production edit.
- The test must keep exercising the real Git-backed move-task gate rather than a helper-only seam, so the wording is pinned through the production path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Pin the absence sentence | As a maintainer, I want `test_a_missing_lane_with_a_sibling_names_conditional_restore` to assert the shipped `the lane branch … does not exist in this checkout` wording so that a softened replacement fails. | High | Open | [ratchet] | no — paired with the mutation control that makes the assertion red |
| FR-002 | Preserve the sibling-path distinctions | As a maintainer, I want the same test to keep proving the lane-tip restore guidance and the absence of the all-lanes-absent claim so that pinning wording does not trade away the branch distinction. | High | Open | [ratchet] | no — same-fixture assertions on the same refusal message |
| FR-003 | Prove the guard is non-vacuous | As a maintainer, I want a recorded red-first proof that the new assertion fails under the `does not exist` → `is unavailable` mutation and passes on shipped source. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Focused test cost | The focused real-Git module completes in under 5 minutes on this host, with no new slow setup beyond the existing fixture. | Performance | Medium | Open |
| NFR-002 | Lint and format | Changed Python passes the repository's scoped `ruff check` and `ruff format --check` with zero findings. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Test-only diff | No file under `src/` changes in the committed diff; the production mutation exists only during the red proof and is reverted. | Technical | High | Open |
| C-002 | One test owner | The absence wording is pinned in the existing Git-backed refusal test named by the issue; do not duplicate it into a second test file. | Technical | High | Open |
| C-003 | No gate weakening | Do not skip, xfail, or relax any existing assertion, marker, or gate to make the suite pass. | Process | High | Open |
| C-004 | Changelog fragment | Add a per-PR `docs/changelog/unreleased/<pr>.internal.md` fragment; do not edit `docs/changelog/CHANGELOG.md`. | Process | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_a_missing_lane_with_a_sibling_names_conditional_restore` fails when the shipped absence sentence is mutated to `is unavailable`, and passes on the unmutated source — [ratchet] · no-op passable: no
- **SC-002**: The real-Git refusal module reports `3 passed` on the final branch — [ratchet] · no-op passable: no
- **SC-003**: `git diff --stat` for the committed change lists only the test file and the changelog fragment — [build] · no-op passable: no
