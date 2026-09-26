# Data Model: Squash Merge Target Safety

## Entities

### BranchIntegrationRequest

| Field | Type | Meaning |
|---|---|---|
| `source_branch` | string | Mission integration branch. |
| `target_branch` | string | Persisted mission target branch. |
| `strategy` | `MergeStrategy` | `squash`, `merge`, or `rebase`. |
| `mode` | enum | Preview or execute. |

### SquashSimulation

| Field | Type | Meaning |
|---|---|---|
| `worktree_path` | temporary path | Detached checkout at the target tip. |
| `target_sha_before` | object id | Atomicity anchor. |
| `merge_command` | argv | Normal `git merge --squash <source>`, without a blanket conflict preference. |
| `unmerged_paths` | ordered tuple of paths | Paths Git could not reconcile. |
| `resolved_planning_paths` | ordered tuple of paths | Conflicts resolved by the existing target-newer planning authority. |

### BranchIntegrationBlocker

| Field | Type | Meaning |
|---|---|---|
| `diagnostic_code` | string | Stable machine-readable blocker identifier. |
| `source_branch` | string | Mission branch that would be integrated. |
| `target_branch` | string | Protected target branch. |
| `conflicting_paths` | ordered tuple of paths | Remaining ungoverned conflicts. |
| `remediation` | list of strings | Operator-visible next actions. |

## Relationships and invariants

1. A `BranchIntegrationRequest` creates exactly one isolated
   `SquashSimulation` when the selected strategy is `squash` and both refs exist.
2. A simulation may delegate only registered artifact paths to custom merge
   drivers and target-newer PRIMARY planning paths to the planning-recency
   authority.
3. Any remaining `unmerged_paths` produce a `BranchIntegrationBlocker`.
4. Preview always discards the simulation and never advances a ref.
5. Execute commits and advances the target only when no blocker exists.
6. Conflict leaves the source ref, target ref, primary checkout bytes, WP states,
   lane branches, and lane worktrees unchanged.
