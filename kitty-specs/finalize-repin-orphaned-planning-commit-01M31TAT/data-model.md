# Data Model: recorded-pin classification (#4827)

This is an infrastructure/CLI fix; the "data model" is the derived classification state of the recorded `planning_commit_sha`, not a persisted schema change. `lanes.json`'s `LanesManifest.planning_commit_sha` field is unchanged (`str | None`).

## Entity: recorded-pin classification (derived, not persisted)

Computed against the **planning target-branch tip** with two git predicates.

| Field | Source |
|-------|--------|
| `recorded_sha` | `LanesManifest.planning_commit_sha` (read from `lanes.json`) |
| `target_tip` | `_capture_target_branch_tip(repo_root, target_branch)` (may be `None`) |
| `object_present` | `git cat-file -e <recorded_sha>^{commit}` → rc 0 |
| `reachable` | `git merge-base --is-ancestor <recorded_sha> <target_tip>` → rc 0 |

### States and transitions

```
execution not begun ............................ CAPTURED   (capture tip; today's behavior)
recorded reachable from tip (rc 0) ............. CURRENT/ADVANCED
recorded present, not reachable, tip capturable  ORPHANED   (the rebase shape)
recorded absent (cat-file rc != 0) ............. FOREIGN
tip uncapturable / not a git repo .............. (degrade → preserve, no classification abort)
```

| From | Action | To |
|------|--------|-----|
| ORPHANED | `finalize --refresh-planning-commit --allow-orphaned` | CURRENT/ADVANCED (re-pinned to tip) |
| ORPHANED | plain `finalize` (no flag) | fail closed (no write); state unchanged |
| ORPHANED | bare `finalize --refresh-planning-commit` | refused ("not an ancestor"); state unchanged |
| FOREIGN | any re-pin attempt | refused; state unchanged |
| CURRENT/ADVANCED | `finalize --refresh-planning-commit` (tip advanced) | refreshed (existing #4141) |

## Consumers of the classification (read-only; C-001 — none writes the field)

| Consumer | File:line | Orphan behavior after fix |
|----------|-----------|---------------------------|
| Recorded-planning merge | `worktree_allocator.py` :419/:482/:562 via shared `_merge_recorded_planning_commit` | raise orphan-specific error naming the re-pin recovery (not generic conflict) |
| Reconcile merge | `implement_support.py:352` (same shared helper) | same as above |
| Claim-ancestry gate | `implement_support.py:497` `check_claim_ancestry` | name orphan + recovery, not bare `missing_refs` |
| Owned-review base | `tasks_move_task.py:697` `_mt_resolve_owned_review_base` | detect orphan (object present ⇒ `rev-parse --verify` succeeds), fail closed instead of diffing a dead base |

## Report vocabulary (FR-009)

`PlanningCommitResolution.action` gains `repinned` alongside the existing `captured` / `preserved` / `refreshed`. The `--json` success payload's `planning_commit` object carries `{action: "repinned", sha, previous_sha, branch_tip}`. `orchestrator_api/envelope.py` `CONTRACT_VERSION` bumps 1.5.0 → 1.6.0 (additive).
