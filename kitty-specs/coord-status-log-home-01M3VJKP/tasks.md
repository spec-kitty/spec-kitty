---
description: "Work package task list for coord-status-log-home-01M3VJKP"
---

# Work Packages: Coordination status log stays off the target branch

**Inputs**: `spec.md`, `plan.md`, `research.md` in `kitty-specs/coord-status-log-home-01M3VJKP/`.

**Organization**: one work package. IC-01, IC-02 and IC-03 touch one product module and its tests, and the characterisation re-pins must land in the same commit as the behaviour change to keep every commit green.

## Subtask Format: `[Txxx] [P?] Description`

Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done --mission coord-status-log-home-01M3VJKP`.

## Mission-wide rules

- **C-004 / NO_FULL_HEAVY_SUITES_IN_MISSION**: named test files only; no `tests/architectural/` directory sweep, no `make test-full`. The new e2e file may be run by name.
- **C-002**: do not edit `src/specify_cli/coordination/commit_router.py` or `src/specify_cli/cli/commands/accept.py`.
- **C-003**: `tests/core/test_mission_create_coord_status_placement.py` stays as adopted from PR #5518.

## Work Package WP01: Seed the coordination status log at create
**Dependencies**: None
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, NFR-001, NFR-002, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003

### Included Subtasks
- T001 Exclude `status.events.jsonl` from the target-branch scaffold for coordination-routed topologies (FR-001, FR-006)
- T002 Materialize the coordination worktree, emit the create events into its mission dir, and commit the log on the coordination branch (FR-002, FR-003)
- T003 Remove the coordination worktree on a failed create, carrying the status log next to the retained scaffold (FR-005)
- T004 Re-pin the characterisation tests per topology and add focused tests for the new helpers (SC-003)
- T005 Add the e2e lifecycle guard, shown red on `main` (FR-004, SC-002)
- T007 Route finalize-tasks lifecycle events to the canonical status surface; no stray primary `status.json` (FR-007)
- T006 Run the targeted validation set and the code-quality gates (NFR-002)

---
