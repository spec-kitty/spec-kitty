# Data Model: Planning lane writes to the Mission branch before landing

No persisted schema changes. This Mission adds derived values only.

## PlanningWriteRef (derived, `mission_runtime`)

| Input | Source |
|---|---|
| `topology_source` | PRIMARY `meta.json` |
| `mission_branch` | PRIMARY `meta.json` |
| `landed` | `mission_runtime.landing.mission_has_landed` |
| `target_branch` | `meta.json` / `lanes.json` |

Rule: `mission_branch` when `topology_source == "default"`, not landed, and `mission_branch` is a non-empty string. Otherwise `target_branch`.

Invariant: an unreadable or malformed `meta.json` raises. It never reads as "not default".

## PlanningWorkspace (derived, `workspace`)

| Field | Value |
|---|---|
| `resolution_kind` | a new distinct value for the Mission-branch checkout. The repository-root kind is unchanged for every other shape. |
| `worktree_path` | `primary_partition_checkout(repo_root, slug)` (the coordination worktree) |
| `branch_name` | `PlanningWriteRef` |

Invariant: when `PlanningWriteRef` is the Mission branch and no checkout holds it, resolution refuses with a named remedy. It never falls back to the repository root.

## PlanningEvidenceWindow (derived, `consolidation.wp_evidence`)

| Shape | Start | End | Granularity |
|---|---|---|---|
| default, not landed | the commit on the Mission branch that introduced the work package's window-opening status event (`window_opener_events` + `commit_introducing_status_event`) | the Mission branch | one window per approved planning work package |
| every other shape | `lanes.json` `planning_commit_sha` | the target branch | one window per lane (unchanged) |

Invariants:
- An unresolved start (no commit, ambiguous, git unavailable) refuses as `EVIDENCE_WINDOW_UNCOMPUTABLE` / `IMPLEMENTATION_UNREADABLE`.
- Non-bookkeeping paths only (`status_only_excluded_prefixes`, unchanged).

## TargetOnlyEvidence (derived, refusal-only)

- Computed only after `IMPLEMENTATION_MISSING` on a default, not-landed planning window.
- Range: `merge-base(planning_commit_sha, target)..target`, limited to the work package's `owned_files`.
- Yields the commit SHAs that changed an owned file. When the list is non-empty, the refusal names them and both remedies.

## State transitions

No new lanes, events or `policy_metadata` keys.
