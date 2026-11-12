# Data model

## ConsolidationState (`.kittify/runtime/merge/<mission_id>/state.json`)
- **New field** `coord_tip_after_projection: str | None` (default `None`).
  - Written with `reconciliation_passed_target_sha` at PASS, and advanced when teardown approves a proven late tip.
  - Cleared and restored together with `reconciliation_passed_target_sha` (one helper).
  - Invariant: non-`None` only while `reconciliation_passed_target_sha` is non-`None`.
  - Legacy records: absent → `None` → resume keeps the pre-mutation base.

## Coordination triple (reclaim target)
| Part | Where | Removed by |
|---|---|---|
| Worktree | `.worktrees/<slug>-coord` (name via `lanes/branch_naming.py`) | `teardown_coordination_topology` |
| Branch | `meta.json` `coordination_branch` | `guarded_branch_delete(..., LANDED_INTENT, expected_tip=tip)` after `is_absorbed` |
| Marker | `meta.json` `coordination_branch` key | `flatten_coordination_metadata` + commit |

Reclaim state transitions: `archived + triple` → (worktree gone) → (branch gone) → (flattened). Each step is idempotent; a re-run resumes at the first remaining part.
