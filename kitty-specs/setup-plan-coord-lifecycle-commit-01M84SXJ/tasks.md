# Tasks: setup-plan commits its lifecycle events on coordination Missions

**Mission**: `setup-plan-coord-lifecycle-commit-01M84SXJ` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

One work package (operator ruling `01M853E34H1MN0CQGQ9209P8MR`: FR-005 is folded into the existing `COORDINATION_WORKTREE_DIRTY` warning, so there is no doctor work package).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first real-CLI tests on an explicit `lanes_with_coord` Mission (commit, scaffold-only, re-run, single_branch regression) | WP01 | |
| T002 | Write the lifecycle events through `write_dir(STATUS_STATE)`, resolved outside the best-effort try | WP01 | |
| T003 | One coordination commit at the end of the run (`commit_for_mission(kind=STATUS_STATE)`) | WP01 | |
| T004 | Fail loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED` (red-first, in-process refusal test) | WP01 | |
| T005 | Surface `lifecycle_commit` in the setup-plan JSON result | WP01 | |
| T006 | Changelog fragment, quality gates and blast-radius run | WP01 | |

## Work Package WP01: setup-plan commits its lifecycle events on the coordination branch

**Goal**: on a coordination Mission, setup-plan's `SpecifyCompleted`, `PlanStarted` and `PlanCompleted` are committed on the coordination branch in the same run, or the run fails loud; every other topology is byte-identical. **Priority**: P1. **Independent test**: `tests/coordination/test_setup_plan_coord_lifecycle_3933.py` through the real CLI.

**Dependencies**: None

Requirement refs: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002, C-003

T001 Red-first real-CLI tests on an explicit `lanes_with_coord` Mission (WP01)
T002 Write the lifecycle events through `write_dir(STATUS_STATE)` (WP01)
T003 One coordination commit at the end of the run (WP01)
T004 Fail loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED` (WP01)
T005 Surface `lifecycle_commit` in the JSON result (WP01)
T006 Changelog fragment, quality gates and blast-radius run (WP01)

**Implementation sketch**: tests first (T001, T004 red), then the placement move (T002, no behaviour change), the commit helper (T003), the refusal (T004), the JSON field (T005), then the fragment and gates (T006).

**Risks**: an unmaterialized coordination worktree (the write-location authority establishes it or refuses with its own named error); a scaffold-only run must still commit; the plan commit must stay untouched; non-coordination topologies must not gain a commit or a JSON key.

Prompt: [tasks/WP01-setup-plan-coord-lifecycle-commit.md](tasks/WP01-setup-plan-coord-lifecycle-commit.md)
