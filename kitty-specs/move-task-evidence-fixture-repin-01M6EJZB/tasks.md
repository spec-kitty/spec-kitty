# Tasks: Re-pin the move-task fixtures refused by the owned-file evidence gate

**Mission**: `move-task-evidence-fixture-repin-01M6EJZB` · **Issue**: #7057 · **Topology**: `single_branch`
**Planning/base branch**: `issue-7057-move-task-evidence-fixture-repin` · **Merge target**: `issue-7057-move-task-evidence-fixture-repin`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Capture the red-first proof on the planning base (`9aed3a8012`): 8 failed / 7 passed, every failure led by `IMPLEMENTATION_MISSING` (FR-004) | WP01 | |
| T002 | Re-pin `git_repo_with_worktree`: WP01 declares `owned_files: src/**` and the lane branch commits `src/implementation.py` inside it, with a comment saying why the declaration is load-bearing (FR-001, FR-002) | WP01 | |
| T003 | `test_move_to_done_with_override_reason_succeeds_when_unmerged` passes `--agent reviewer-renata`, the identity #6715's independence gate requires for a `done` move (FR-003) | WP01 | |
| T004 | Re-run the module (15 passed) plus the move-task surfaces that share the fixture helper, and the #6715 gate tests unchanged (NFR-001, NFR-003, SC-004) | WP01 | |
| T005 | Add the internal changelog fragment; run `check_changelog_style` and `check_spelling --pass unreleased` (C-003) | WP01 | [P] |
| T006 | Prove scope discipline: `git diff` against the planning base touches no `src/` path, and the module still collects 15 nodes with unchanged markers (FR-004, SC-003) | WP01 | |

## WP01 — Re-pin the move-task evidence fixtures (P1)

**Goal**: the 8 out-of-matrix nodes refused by #6715's owned-file evidence gate pass on honest fixture evidence, and the gate itself is untouched (FR-001–FR-004, NFR-001–NFR-003, C-001–C-003, SC-001–SC-004).
**Independent test**: `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` is 8 failed / 7 passed on the planning base and 15 passed on the branch.
**Prompt**: [tasks/WP01-repin-move-task-evidence-fixtures.md](tasks/WP01-repin-move-task-evidence-fixtures.md)

T001 Capture the red-first proof on the planning base (WP01)
T002 Re-pin the fixture's ownership and owned commit (WP01)
T003 Name the approver in the done-override node (WP01)
T004 Re-run the module and the neighbouring move-task surfaces (WP01)
T005 Internal changelog fragment and its style checks (WP01)
T006 Prove scope discipline and an unchanged node set (WP01)

**Dependencies**: none. **Risks**: an unowned root deliverable (the pre-fix `implementation.txt`) is what triggers the gate, so the commit must land under the lane's `src/**` write scope; and the done-override node must supply a non-generic `--agent`, or #6715's independence gate refuses it for the right reason.
