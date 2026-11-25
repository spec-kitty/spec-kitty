---
description: "Work packages for the stale-lane sibling recovery Mission"
---

# Work Packages: Recoverable stale-lane refusal after a halted in-run auto-rebase

**Inputs**: `kitty-specs/stale-lane-sibling-recovery-01M7X1QS/` (spec.md, plan.md, research/code-grounding.md)

One work package: the change is a single concern (IC-01) in two closely coupled modules, and splitting it would leave a red reproduction between packages.

## Work Package WP01: Accurate, recoverable stale refusal (Priority: P0)

**Goal**: The stale refusal at `consolidate` carries the auto-rebase halt reason, names the sibling lane branch, and prints a remedy valid for an approved work package; following it lets the next run pass the lane.
**Independent Test**: `tests/consolidation/test_7755_stale_sibling_lane_recovery.py` drives `spec-kitty consolidate`, follows the printed remedy, and re-runs to a landing.
**Prompt**: `tasks/WP01-recoverable-stale-refusal.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, C-001, C-002, C-003

### Included Subtasks

| ID | Description |
|----|-------------|
| T001 | Red-first: un-mark the #7755 `p0_repro` test; add the CLI recovery test and its fixture; show both red on pre-fix sources. |
| T002 | `stale_check`: `SiblingLane`, `find_sibling_lanes`, `refine_stale_result`, result fields; remedy text with the reopen step (#7754). |
| T003 | `lanes/consolidation`: carry the halt reason, compute sibling candidates via `lane_branch_name`, refine before rendering. |
| T004 | Unit tests for the new helpers and remedy branches; update pinned remedy texts. |
| T005 | CLAUDE.md canon sentence, changelog fragment, gates, ruff/mypy. |

### Dependencies

None.
