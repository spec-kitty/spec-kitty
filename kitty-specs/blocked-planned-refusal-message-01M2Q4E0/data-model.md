# Phase 1 Data Model: Source-aware unblock refusal message

No persisted data model changes. This mission touches an in-memory decision
request and reads (never mutates) the lane state machine. The "model" here is
the lane→reachability partition that shapes the message.

## Entities

### MoveTaskRequest (existing; read-only for this change)

Relevant fields consumed by `_guard_planned_rollback`:

| Field | Meaning | Used to… |
|-------|---------|----------|
| `target_lane` | The requested destination lane | Gate on `== Lane.PLANNED` (unchanged) |
| `old_lane` | The work package's current/source lane (may be an alias, e.g. `doing`) | **NEW:** resolve → lane → `allowed_targets()` to shape the message |
| `force` | Whether `--force` was passed | Deliberately **unread** by this guard (force-proofness) — unchanged |
| `feedback_provided` / `feedback_exists` / `feedback_is_file` / `feedback_content` | Review-feedback file facts | The four allow/deny checks (unchanged) |

### Lane state (existing; read-only accessor)

`wp_state_for(lane).allowed_targets() -> frozenset[Lane]` — the state machine's
own declaration of legal outgoing edges. Source of truth for the legal-target
list; the message never hard-codes a lane set.

## Reachability partition (the new derived fact)

`planned_reachable(old_lane) := Lane.PLANNED in wp_state_for(resolve_lane_alias(old_lane)).allowed_targets()`

| Source lane | `allowed_targets()` | `planned` reachable? | Message arm |
|-------------|---------------------|----------------------|-------------|
| `in_review` | includes `planned` | yes | review-feedback (existing text) |
| `in_progress` | includes `planned` | yes | review-feedback (existing text) |
| `approved` | includes `planned` | yes | review-feedback (existing text) |
| `genesis` | `{canceled, planned}` | yes | review-feedback (existing text) |
| `blocked` | `{in_progress, canceled}` | no | legal-targets; name `--to in_progress` resume |
| `canceled` | `{}` (terminal) | no | legal-targets (terminal — no targets) |
| `done` | `{}` (terminal) | no | legal-targets (terminal — no targets) |
| `uninitialized` | `{}` | no | legal-targets (no targets) |

Note: the partition is computed, not enumerated in code — any future change to a
lane's `allowed_targets()` re-partitions automatically.

## Invariants

- **INV-1 (force-proof):** for every source lane and every `force` value, a
  `--to planned` move without a valid non-empty review-feedback file returns
  `RefuseExit1` (lane unchanged). The reachability fact selects *wording only*.
- **INV-2 (no state-machine dependency inversion):** the guard reads
  `allowed_targets()` but never calls `check_transition`/`build_transition_plan`;
  it cannot proceed to an emit as a side effect of computing the message.
- **INV-3 (no resurrection event):** a refused move emits no status transition
  event (no `force=true` rewind out of `done`).
