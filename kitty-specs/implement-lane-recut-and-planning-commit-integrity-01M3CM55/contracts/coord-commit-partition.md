# Contract: coordination-commit path partition (#4905)

**Surface**: `src/specify_cli/cli/commands/agent/workflow.py::_commit_via_coordination_transaction` — the shared sink through which every coord lifecycle staging site funnels.

## Staging sites covered (all funnel here)
- `cli/commands/agent/workflow_executor.py:881` — claim (`planned → claimed`, `paths=[wp_path, *status_artifacts]`)
- `:1066` — resume-refresh (`_implement_emit_resume_refresh`)
- `:1741` — review-claim (`for_review → in_review`)

## Behaviour
For each path in the transaction's `paths`, classify by artifact kind (`mission_runtime.is_primary_artifact_kind`):
- **PRIMARY-partition** (`WORK_PACKAGE_TASK`, spec/plan/tasks): route to the PRIMARY target via the existing `commit_to_primary_target` mechanism — **never** written into the coord worktree / committed to the coordination branch.
- **STATUS_STATE** (`status.events.jsonl`, `status.json`): committed to the coordination branch as today.

## Invariant
The coordination branch tree contains **zero** `kitty-specs/<slug>/tasks/WP*.md` blobs at every lifecycle point. Consequently the next lane cut from the coord tip carries no WP file, and `_merge_recorded_planning_commit` (FR-009 planning merge, `worktree_allocator.py`) completes without an add/add conflict.

## Regression assertions (must be RED pre-fix)
1. After `agent action implement WP01` on a coord mission → coord tree has no `tasks/WP01-*.md` blob.
2. After WP01 review-claim (`for_review → in_review`) → coord tree still has no `tasks/WP*.md` blob (multi-site coverage).
3. `agent action implement WP02` → lane allocated, planning merge succeeds, no `PlanningCommitMergeConflictError`, exit 0.
4. `lanes` topology (no coord) → unchanged (control).
