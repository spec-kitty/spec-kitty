---
work_package_id: WP02
title: Planning-data-loss suite re-pins
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-002
- FR-004
planning_base_branch: claude/lucid-ptolemy-fjtzep
merge_target_branch: claude/lucid-ptolemy-fjtzep
branch_strategy: Planning artifacts for this mission were generated on claude/lucid-ptolemy-fjtzep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/lucid-ptolemy-fjtzep unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
phase: Phase 1 - Remediation
history:
- at: '2026-09-26T11:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/integration/test_merge_lane_planning_data_loss.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Planning-data-loss suite re-pins

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing.

---

## Objectives & Success Criteria

- `tests/integration/test_merge_lane_planning_data_loss.py` passes in full: 8 tests red today across causes A, B and C2.

## Context & Constraints

- This file hosts three causes, so one WP owns it.
- Product changes: 2fd7eabf01 (coord fail-closed), 6545dc532f (#5001 reconciliation claim), and the LanesManifest identity invariant (`src/specify_cli/lanes/models.py:145`: ULID or None, never a slug).
- Depends on WP03, because the dry-run retention test goes through the forecast path that WP03 hardens.

## Subtasks & Detailed Guidance

### Subtask T005 – Retention tests materialize the coordination worktree (cause A)

- **Tests**: `TestRetentionConstraintSurvivesCleanup` × 4 (~lines 1473, 1582, 1678, 1763).
- **Steps**:
  - After the fixture creates the coordination branch (~line 1497), materialize its worktree. Follow the opt-in helper pattern from 42adce94: see `_materialize_coord_worktree` in `tests/mission_runtime/test_coord_read_seam.py`, or the equivalent in `tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py`.
  - Make sure the approved status events live on the coordination surface the merge reads.
  - Keep the retention assertions untouched.

### Subtask T006 – wp_order planning-lane test (cause B)

- **Test**: `TestMergeIncludesPlanningLane::test_merge_state_wp_order_includes_planning_lane_wps`.
- **Steps**: Stub `specify_cli.merge.executor._capture_reconciliation_claim` and `_phase_reconcile_before_teardown`, exactly as 26be43c804 did. A comment explains that the test's subject is `wp_order`, while reconciliation is covered by `tests/merge/test_reconciliation.py` and `tests/terminus`.

### Subtask T007 – Valid mission identity (cause C2)

- **Tests**: `TestPlanningArtifactReachesTarget` × 2.
- **Steps**: The fixture at ~line 317 writes `mission_id=<slug>`. Write `mission_id=None` (legacy lane naming), which makes the claim resolve the real lane branch. A comment cites the invariant. Do NOT stub the reconciliation gate here: it is part of what the test proves.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_merge_lane_planning_data_loss.py -q
```

## Risks & Mitigations

- The materialize helper may be test-module-private. Copy the minimal logic locally rather than importing across test packages, and cite the source.

## Branch Strategy

- **Strategy**: single_branch mission; the execution workspace is resolved per computed lane from `lanes.json`.
- **Planning base branch**: `claude/lucid-ptolemy-fjtzep`
- **Merge target branch**: `claude/lucid-ptolemy-fjtzep`

## Definition of Done

- Every listed test passes locally.
- No test is skipped, xfailed, deleted or retried (C-001).
- `ruff check` and `ruff format --check` are clean on the touched files.
- Every re-pin carries a docstring or comment citing the product change that moved the contract.

## Activity Log

- 2026-09-26T11:30:00Z – system – Prompt created.
