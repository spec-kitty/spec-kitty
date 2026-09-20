# Data Model — Terminus-Safety Invariant

This is a control-flow / invariant mission, not a schema mission. The "entities" are the readers,
predicates, and checkpoints the invariant is built from.

## Predicates (the terminal vocabulary — kept DISTINCT, D4)

| Predicate | Definition | Home | Used by |
|-----------|-----------|------|---------|
| `is_acceptable_ending(lane, *, has_provenance)` | approved/done → True; canceled → True iff provenance; else False | `status_lanes.py:82` (existing) | the aggregate below |
| **`mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)`** *(NEW, WP01)* | every non-excluded WP is at an acceptable ending; returns the missing set | `status_lanes.py` (pure, provenance-aware) | merge precond, accept, close-adjacent |
| **merge-ready** | all non-cancelled WPs ∈ {approved, done} ∪ acceptably-cancelled | derived from the aggregate | `merge` precondition (FR-001) |
| **merged** | a merge baseline recorded (`merged_at` present) | `status/lifecycle.py:294` `is_mission_merged` | `mission close` guard (FR-004) |
| **completed** | merged OR all-terminal | `status/lifecycle.py:320` `is_mission_completed` | `reopen` (existing precedent) |

Invariant: `warn` gate mode may soften evidence-QUALITY predicates (review verdict, risk,
hollow-review) but NEVER the merge-ready predicate (FR-003).

## State transitions guarded

```
merge:   [gates+precondition] --refuse-if-not-merge-ready--> (no mutation)
                              --pass--> consolidate → bake → record-done → (rollback on failure)
close:   [precondition] --refuse-if-not-merged--> (no writes, no teardown)
                        --pass--> persist retrospective → teardown coord worktree
accept:  [summary.ok gate] --refuse--> (no mutation)   (already gate-then-mutate; reroute readiness)
```

## Coordination checkpoint (NEW, WP05 — unifies existing fragments)

| Field | Meaning |
|-------|---------|
| pre-mutation coord ref SHA | coordination branch tip captured BEFORE `consolidate_lane_into_mission` |
| pre-mutation coord worktree state | for reset coherence with committed `done` markers |
| pre-done coord ref SHA | existing `_capture_pre_target_coord_ref_sha` boundary, folded into the same primitive |
| target ref (direct-on-target only) | pre-advance target tip for the direct-on-target rollback arm (D5) |

Reset semantics: on a post-mutation failure, reset coord ref (+ worktree, + target on direct-on-target)
to the pre-mutation checkpoint so `--resume` reads a coherent state
(`_durable_done_wps_on_coordination_ref`, `done_bookkeeping.py:598`). Rollback runs BEFORE
`_phase_cleanup_worktrees_and_branches` (`executor.py:1588`) — after teardown, `_coord_worktree_root`
returns None and a reset silently no-ops.

## meta.json fields touched

| Field | Concern |
|-------|---------|
| `mission_number` | FR-006 (never baked when not-merge-ready) + FR-011 (topology-aware write-back on merge-ready coord mission; no silent loss) |
| `merged_at` / baseline merge commit | read by the close guard (FR-004) and re-evaluated live on `--resume` (FR must not pass vacuously, US1-5) |
| `coordination_branch` | FR-013 — `mission close` tolerates an orphaned marker |
