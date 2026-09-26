# Work Packages: Nightly red remediation (run 36225024230)

**Inputs**: Design documents from `kitty-specs/nightly-red-remediation-01M3EP85/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Required. This mission is test remediation plus red-first product fixes (C-001, C-002).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`). Ownership is split per file: `test_merge_lane_planning_data_loss.py` hosts causes A, B and C2, so it belongs to exactly one work package (WP02).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel.
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Re-pin surface-seam unmaterialized test to the fail-closed contract | WP01 | [P] |
| T002 | Re-pin Guard4 split-brain unmaterialized test to the fail-closed contract | WP01 | [P] |
| T003 | Arbiter fixture writes lanes.json; add guard negative cell | WP01 | [P] |
| T004 | Retrospect smoke fixture seeds causal rework before approval | WP01 | [P] |
| T005 | Retention tests materialize the coordination worktree | WP02 | |
| T006 | wp_order planning-lane test stubs the reconciliation phases | WP02 | |
| T007 | Planning-artifact fixture writes a valid mission identity (mission_id=None) | WP02 | |
| T008 | Clean `merge --dry-run` refusal on unmaterialized/deleted coordination (red-first) | WP03 | |
| T009 | Reproduce fresh-merge pre-mutation stop wedging the next merge (red-first) | WP03 | |
| T010 | Clear the fresh run's own state on any pre-mutation gate-phase exit | WP03 | |
| T011 | `merge --abort` removes the reconciliation post-fix marker | WP03 | |
| T012 | Post-merge index-refresh tests stub the reconciliation phases | WP04 | [P] |
| T013 | Untracked-tolerance tests stub the reconciliation phases | WP04 | [P] |
| T014 | Sparse refresh/invariant tests stub the reconciliation phases | WP04 | [P] |
| T015 | Resume tests (incl. 30s perf budget) seed a post-fix resume state | WP04 | |
| T016 | Lane-worktree and primary-checkout safety fixtures seed WP01 approved | WP04 | [P] |
| T017 | Bound the interpreter suite step inside the job cap; per-test timeout | WP05 | [P] |
| T018 | Nightly summary fails closed on any non-success leg | WP05 | [P] |
| T019 | Workflow-shape tests for T017/T018 | WP05 | |
| T020 | Re-aim the doctor-ops large-spine sweep gate at the close loop | WP05 | [P] |

---

## Work Package WP01: Non-merge integration fixture re-pins (Priority: P1)

**Goal**: Re-pin the coordination-seam, arbiter-override and retrospect-smoke tests to the current product contracts.
**Independent Test**: The 6 affected tests pass, and the new guard negative cell passes.
**Prompt**: `tasks/WP01-non-merge-integration-fixture-re-pins.md`
**Requirement Refs**: FR-001, FR-006, FR-007

### Included Subtasks

T001 Re-pin surface-seam unmaterialized test to the fail-closed contract (WP01)
T002 Re-pin Guard4 split-brain unmaterialized test to the fail-closed contract (WP01)
T003 Arbiter fixture writes lanes.json; add guard negative cell (WP01)
T004 Retrospect smoke fixture seeds causal rework before approval (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Asserting a raise must not hide a second split-brain read path; record the finding if `resolve_feature_dir_for_mission` still falls back silently.

---

## Work Package WP02: Planning-data-loss suite re-pins (Priority: P1)

**Goal**: Bring all of `tests/integration/test_merge_lane_planning_data_loss.py` (causes A, B and C2) green.
**Independent Test**: The file passes in full.
**Prompt**: `tasks/WP02-planning-data-loss-suite-re-pins.md`
**Requirement Refs**: FR-001, FR-002, FR-004

### Included Subtasks

T005 Retention tests materialize the coordination worktree (WP02)
T006 wp_order planning-lane test stubs the reconciliation phases (WP02)
T007 Planning-artifact fixture writes a valid mission identity (mission_id=None) (WP02)

### Dependencies

- Depends on WP03, because the dry-run retention test goes through the forecast path that WP03 hardens.

---

## Work Package WP03: Merge product defects (Priority: P1)

**Goal**: `merge --dry-run` refuses cleanly on unmaterialized coordination, and a fresh merge that stops before mutation never wedges the next run.
**Independent Test**: The new red-first regressions fail on the base and pass after the fix; existing merge tests stay green.
**Prompt**: `tasks/WP03-merge-product-defects.md`
**Requirement Refs**: FR-008, FR-009

### Included Subtasks

T008 Clean `merge --dry-run` refusal on unmaterialized/deleted coordination (red-first) (WP03)
T009 Reproduce fresh-merge pre-mutation stop wedging the next merge (red-first) (WP03)
T010 Clear the fresh run's own state on any pre-mutation gate-phase exit (WP03)
T011 `merge --abort` removes the reconciliation post-fix marker (WP03)

### Dependencies

- None.

---

## Work Package WP04: Merge-path integration fixture re-pins (Priority: P1)

**Goal**: Re-pin the remaining merge-path integration tests (causes B, C1, C3) and the perf-suite resume budget test.
**Independent Test**: The 13 affected tests pass, including `test_resume_completes_within_30s_budget` under `SPEC_KITTY_RUN_PERFORMANCE=1`.
**Prompt**: `tasks/WP04-merge-path-integration-fixture-re-pins.md`
**Requirement Refs**: FR-002, FR-003, FR-005

### Included Subtasks

T012 Post-merge index-refresh tests stub the reconciliation phases (WP04)
T013 Untracked-tolerance tests stub the reconciliation phases (WP04)
T014 Sparse refresh/invariant tests stub the reconciliation phases (WP04)
T015 Resume tests (incl. 30s perf budget) seed a post-fix resume state (WP04)
T016 Lane-worktree and primary-checkout safety fixtures seed WP01 approved (WP04)

### Dependencies

- Depends on WP03 (executor pre-mutation state handling changes).

---

## Work Package WP05: Nightly lanes fail closed + sweep gate re-aim (Priority: P2)

**Goal**: An overrunning nightly interpreter leg still escalates and fails, the summary fails closed, and the doctor-ops sweep gate measures the close loop.
**Independent Test**: New tests in `tests/ci/` pass; `test_doctor_ops.py` performance tests pass 3 times in a row.
**Prompt**: `tasks/WP05-nightly-lanes-fail-closed-and-sweep-gate.md`
**Requirement Refs**: FR-010, FR-011

### Included Subtasks

T017 Bound the interpreter suite step inside the job cap; per-test timeout (WP05)
T018 Nightly summary fails closed on any non-success leg (WP05)
T019 Workflow-shape tests for T017/T018 (WP05)
T020 Re-aim the doctor-ops large-spine sweep gate at the close loop (WP05)

### Dependencies

- None.
