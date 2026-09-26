# Data Model: Implement lane-allocation integrity

Phase 1 output. No persistent schema changes; this captures the decision state the two fixes reason over.

## Entities / value objects

### WorkspaceContext (existing — `src/specify_cli/workspace/context.py`)
Persisted at `.kittify/workspaces/<slug>-lane-<id>.json`. Read by the #4889 detector; **never mutated on the fail-closed path** (FR-003).

| Field | Meaning for this mission |
|-------|--------------------------|
| `branch_name` | the lane branch the detector reports as missing (e.g. `kitty/mission-<slug>-lane-a`) |
| `base_commit` | the SHA the lane was cut from; recovery anchor |
| `lane_id` | lane the WP belongs to |
| `current_wp` / `wp_id` | active WP |
| `created_at` | prior-allocation timestamp (presence ⇒ the lane was allocated before) |

Existence of this record for a lane is the load-bearing "this lane was allocated before" signal.

### Lane allocation route (existing — `allocate_lane_worktree`)
Ordered decision. #4889 inserts a pre-flight **before** the FRESH routes.

### WP lane state (existing — `status.events.jsonl` reduced)
Non-terminal post-allocation set the detector keys on: `{in_progress, blocked, for_review, in_review}`. Terminal (`done`, `canceled`) and pre-allocation (`planned`, `claimed`) are **not** triggers.

## #4889 destroyed-lane decision table

Inputs: `WT` = lane worktree exists; `BR` = local lane branch exists; `CTX` = persisted WorkspaceContext exists; `STATE` = canonical WP lane state; `REACH` = the cut-from base (`WorkspaceContext.base_commit`, a proxy for the lane's work tip — the work tip is not persisted) is an ancestor of the target branch.

| WT | BR | CTX | STATE | REACH | Route / outcome |
|----|----|-----|-------|-------|-----------------|
| yes | — | — | any | — | **REUSE** (no-op resume) — unchanged (FR-004) |
| no | yes | — | any | — | **CRASH_RECOVERY** (re-attach) — unchanged (FR-004) |
| no | no | no | any | — | **FRESH** — genuinely new lane, create normally (FR-001 no false positive) |
| no | no | yes | terminal (`done`/`canceled`) | — | normal routing (not a trigger) |
| no | no | yes | non-terminal | **yes** | resume/recreate — tip already on target, no work stranded (FR-009) |
| no | no | yes | non-terminal | **no** | **FAIL CLOSED** (FR-002): exit non-zero, diagnostic names `branch_name` + recovery ref, no `Lane worktree ready`, CTX untouched (FR-003) |

The last row is the #4889 defect condition. The guard sits inside `allocate_lane_worktree` so both the CLI (`create_lane_workspace`) and orchestrator-api (`_resolve_start_workspace`) callers are covered (FR-008).

## #4905 coord-commit path partition

At the shared sink `_commit_via_coordination_transaction` (`cli/commands/agent/workflow.py`), each staged path is classified before it is written into the coord worktree:

| Path kind (`mission_runtime.is_primary_artifact_kind`) | Example | Destination |
|--------------------------------------------------------|---------|-------------|
| PRIMARY-partition (`WORK_PACKAGE_TASK`, spec/plan/tasks) | `kitty-specs/<slug>/tasks/WP01-*.md` | PRIMARY target (via `commit_to_primary_target`) — **never coord** |
| STATUS_STATE (coord-owned) | `status.events.jsonl`, `status.json` | coordination branch |

Applies uniformly to all three staging sites (claim / resume-refresh / review-claim) because they all funnel through this sink (FR-005). Result: a lane cut from the coord tip no longer carries the WP file, so the FR-009 `_merge_recorded_planning_commit` on the next lane has no add/add conflict (FR-006).

## Invariants

- INV-1: `implement` never reports success (`Lane worktree ready`, exit 0) when the WP's committed work is unreachable from the produced lane.
- INV-2: the coordination branch tree contains zero `tasks/WP*.md` blobs at any point in the lifecycle.
- INV-3: the fail-closed path is side-effect-free w.r.t. persisted lane metadata (recovery pointer preserved).
