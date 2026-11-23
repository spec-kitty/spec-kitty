---
description: "Work packages for One landing proof for lane cleanup"
---

# Work Packages: One landing proof for lane cleanup

**Inputs**: `kitty-specs/lane-cleanup-landing-proof-01M81KHJ/` (spec.md, plan.md, research.md, data-model.md, contracts/landing-proof.md, quickstart.md)
**Tests**: required (ATDD red-first, charter C-011; diff-cover ≥ 90 %; `src/specify_cli/lanes/*` is a diff-cover critical path since #7789).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first acceptance: a real squash landing removes every lane | WP01 | |
| T002 | Red-first unit rules of the landing proof (positives and negatives) | WP01 | [P] |
| T003 | Lane-own commits and authored paths helpers | WP01 | |
| T004 | Public predicate with the per-path rules | WP01 | |
| T005 | Consolidate adoption; delete the private status-log proof; re-pin the #6736 import | WP01 | |
| T006 | ADR 2026-11-06-1 amendment to O3 | WP01 | [P] |
| T014 | `accept --mode pr` lane cleanup passes the Mission slug (G1, ruling 3A) | WP01 | |
| T007 | Red-first doctor unit tests (released lane vs other worktree) | WP02 | |
| T008 | Red-first doctor acceptance on a real landing pushed to origin | WP02 | [P] |
| T009 | Released Mission slug resolver | WP02 | |
| T010 | Doctor assessment and guard proof adopt the predicate | WP02 | |
| T011 | Red-first tests for the proof-unavailable legs | WP03 | |
| T012 | Keep the lane with `LANDING_PROOF_UNAVAILABLE` | WP03 | |
| T013 | Kept line: remedy, backstop only with a worktree, docstrings | WP03 | |

---

## Work Package WP01: The landing proof and consolidate adoption (Priority: P1)

**Goal**: one public predicate proves a lane landed while setting aside only Mission bookkeeping the lane never authored; consolidate's lane cleanup uses it, and every lane of a clean squash landing is removed.
**Independent Test**: `tests/integration/test_lane_cleanup_landing_proof_7747.py` (real CLI) and `tests/lanes/test_lane_tip_mission_bookkeeping.py`.
**Prompt**: `tasks/WP01-landing-proof-and-consolidate.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-009, NFR-001, NFR-002, NFR-003, C-001, C-002, C-004, SC-001, SC-003

### Included Subtasks

T001 Red-first acceptance: a real squash landing removes every lane (WP01)
T002 Red-first unit rules of the landing proof (WP01)
T003 Lane-own commits and authored paths helpers (WP01)
T004 Public predicate with the per-path rules (WP01)
T005 Consolidate adoption; delete the private status-log proof; re-pin the #6736 import (WP01)
T006 ADR 2026-11-06-1 amendment to O3 (WP01)
T014 `accept --mode pr` lane cleanup passes the Mission slug (G1, ruling 3A) (WP01)

### Implementation Notes

- Order inside the predicate: ancestor → authorship → merge-tree judged outside `kitty-specs/` only → per-path rules under `kitty-specs/` (research R3). Never call plain `is_absorbed` first.
- Any `GitCommandError` → `False`.

### Dependencies

- None.

### Risks & Mitigations

- A merge driver making a lane look landed: the merge-driver negative pins it, with plain `is_absorbed` as the control.

---

## Work Package WP02: Doctor adopts the landing proof (Priority: P1)

**Goal**: `doctor workspaces` rates a released Mission's lanes with the same predicate, so `--prune` clears what consolidate printed as its remedy.
**Independent Test**: `tests/specify_cli/workspace/test_landed_worktrees_mission_bookkeeping.py`; `tests/integration/test_doctor_prunes_landed_mission_lanes_7747.py`.
**Prompt**: `tasks/WP02-doctor-adopts-landing-proof.md`
**Requirement Refs**: FR-001, FR-007, SC-002

### Included Subtasks

T007 Red-first doctor unit tests (WP02)
T008 Red-first doctor acceptance on a real landing pushed to origin (WP02)
T009 Released Mission slug resolver (WP02)
T010 Doctor assessment and guard proof adopt the predicate (WP02)

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Applying the set-aside to a non-Mission worktree: only released Mission lanes get the slug (ruling 4); a negative pins the plain proof elsewhere.

---

## Work Package WP03: No lane leaves through the older remover without a proof (Priority: P2)

**Goal**: a lane with no usable landing proof is kept with `LANDING_PROOF_UNAVAILABLE`, its branch untouched (#7325).
**Independent Test**: `tests/consolidation/test_lane_remover_proof_unavailable_7325.py`.
**Prompt**: `tasks/WP03-proof-unavailable-keeps-lane.md`
**Requirement Refs**: FR-008, C-001, C-003, SC-003

### Included Subtasks

T011 Red-first tests for the proof-unavailable legs (WP03)
T012 Keep the lane with `LANDING_PROOF_UNAVAILABLE` (WP03)
T013 Kept line: remedy, backstop only with a worktree, docstrings (WP03)

### Dependencies

- Depends on WP01 (same module, sequential).

### Risks & Mitigations

- Retention regressions: the retained-branch leg keeps today's worktree removal (plan PD-1); its existing tests must stay green.
