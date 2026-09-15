# Data Model: Blocked-WP unblock path (#3937)

No storage schema changes. The relevant model is the WP lifecycle FSM and the allocation-failure control flow.

## Entities

### Work Package lane (existing `Lane` StrEnum)
`planned → claimed → in_progress → for_review → in_review → approved → done`; `blocked` reachable from all non-terminal; `canceled` reachable from all. Authoritative transition matrix = per-state `allowed_targets()` (`wp_state.py`). `ALLOWED_TRANSITIONS` in `transitions.py` is a non-authoritative projection.

### BlockedState (existing)
`allowed_targets() = {in_progress, canceled}`. Therefore `blocked → planned` is **illegal**. This mission does NOT change this set (C-001).

## Allocation-failure control flow (the F-50 fix, behavior delta)

```
implement WP##
  ├─ create_lane_workspace(WP)        # may raise DependencyLaneMergeConflictError / PlanningCommitMergeConflictError
  │     (allocator aborts + reset --hard; lanes.json NOT written)   ← WP still `planned`
  ├─ [claim transition planned→claimed]   # only reached on success
  └─ except (alloc failure):
        BEFORE: _emit_blocked_on_alloc_failure()  → emits planned→blocked   ← DEFECT (unrecoverable)
        AFTER : print exc.next_step (actionable) ; WP stays `planned`       ← FIX (recoverable, reentrant)
```

Invariant enforced by the fix: **a tooling/allocation failure emits no lifecycle transition** — the WP's lane is unchanged. Only a successful claim moves it forward; only a genuine domain block emits `blocked`.

## Transition-refusal model (the F-51 fix, behavior delta)

`move-task --to <target>` guard sequence (unchanged order):
```
… → _guard_planned_rollback → … → (FSM legality at emit)
```
- BEFORE: `_guard_planned_rollback` fires for ANY `target==planned` regardless of source → demands `--review-feedback-file` before legality is checked.
- AFTER: `_guard_planned_rollback` early-returns when `source` (old_lane) is not a review-family lane → `blocked→planned` reaches FSM legality → refused as illegal transition, message enumerates `{in_progress, canceled}` (sourced from `allowed_targets()`, CLI/emit path only).

Review-family source lanes (feedback requirement STILL applies): the existing set that legitimately rolls back to `planned` with review feedback (e.g. `in_review`, `for_review`). Non-review sources (e.g. `blocked`) fall through to legality.

## Events
No new event types. `status.events.jsonl` gains **fewer** rows (no manufactured `blocked` on alloc failure); no format change.
