# Work Packages: Lane worktree status shadow authority

**Inputs**: Design documents from `kitty-specs/lane-worktree-status-shadow-authority-01M68JFG/`
**Prerequisites**: plan.md, spec.md

**Tests**: Required. The charter's ATDD-first rule applies: the WP opens with a failing test
through the pre-existing read-path entry point, committed before the implementation commit.

**Organization**: One work package. The defect is a single seam plus its regression fixture, so a
second WP would split one commit-worthy change.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression test: a status read anchored at a lane worktree root returns the authoritative lane, not the fork-time shadow | WP01 | |
| T002 | Non-vacuity controls: coordination husk keeps its authority, independent clone keeps its own, same-fixture authoritative read | WP01 | [P] |
| T003 | Re-anchor a lane-worktree root to the repository's main worktree root in the guarded read-side seam | WP01 | |
| T004 | Changelog `[Unreleased]` entry with the before/after and the `(#6466)` reference | WP01 | [P] |

---

## Work Package WP01: A lane worktree root is not a status surface (Priority: P2)

**Goal**: A status read anchored at a lane worktree root resolves the mission's authoritative
status surface (coordination husk when the mission routes through coordination, the
primary/mission-branch copy otherwise) instead of the lane worktree's fork-time copy, so a
routine `for_review` transition never demands `--force`.
**Independent Test**: `pytest tests/specify_cli/missions/test_lane_worktree_status_shadow.py`
**Prompt**: `tasks/WP01-lane-worktree-root-is-not-a-status-surface.md`
**Requirement Refs**: FR-001, FR-002, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red-first regression test for the lane-worktree shadow read (WP01)
T002 [P] Non-vacuity controls: coordination husk, independent clone, authoritative same-fixture read (WP01)
T003 Re-anchor a lane-worktree root in the guarded read-side seam (WP01)
T004 [P] Changelog `[Unreleased]` entry (WP01)
