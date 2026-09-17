# Contract: `move-task --to planned` refusal message

Behavioral contract for `_guard_planned_rollback`
(`src/specify_cli/cli/commands/agent/tasks_transition_core.py`). This contract
defines *observable* behavior; it is deliberately expressed without a YAML/JSON
schema block (no serialized artifact is defined here).

## Preconditions

- The move request targets `planned` (`target_lane == Lane.PLANNED`).
- No valid, non-empty review-feedback file is supplied
  (`not (feedback_provided and feedback_exists and feedback_is_file and feedback_content.strip())`).

## Guarantees (invariant across all source lanes and `force` values)

- **G-1**: The decision is `RefuseExit1` (the CLI exits non-zero); the work
  package lane is unchanged.
- **G-2**: No status transition event is emitted (in particular, no `force=true`
  rewind event out of a terminal lane).
- **G-3**: The refusal is produced by `_guard_planned_rollback` *before* the
  state machine is consulted; no source lane reaches `build_transition_plan`.

## Message shape (the only behavior that changes)

Let `reachable = Lane.PLANNED in wp_state_for(resolve_lane_alias(old_lane)).allowed_targets()`.

### Arm A — `reachable` is true (`in_review`, `in_progress`, `approved`, `genesis`)

The message is the **existing** text, unchanged:

- contains `requires review feedback`
- contains the `--review-feedback-file feedback.md` guidance
- contains `This requirement cannot be bypassed with --force.`

### Arm B — `reachable` is false (`blocked`, `canceled`, `done`, `uninitialized`)

The message:

- MUST NOT contain `requires review feedback`.
- MUST state that `planned` is not reachable from the source lane.
- MUST name the source lane's legal targets from `allowed_targets()`, or state
  the lane is terminal when the set is empty (`done`, `canceled`).
- For `blocked` specifically, MUST name `--to in_progress` as the resume path
  (and MAY name `--to canceled`).

## Worked cases (acceptance)

| Source | `--force` | feedback file | Result | Message arm |
|--------|-----------|---------------|--------|-------------|
| `blocked` | no | none | refuse, stays `blocked` | B — names `--to in_progress` |
| `blocked` | yes | none | refuse, stays `blocked` | B |
| `blocked` | no | fabricated non-empty | refuse, stays `blocked` | B (feedback cannot launder an illegal transition) |
| `done` | no | none | refuse, stays `done`, no rewind event | B — terminal |
| `done` | yes | none | refuse, stays `done` | B — terminal |
| `canceled` | no/yes | none | refuse, stays `canceled` | B — terminal |
| `genesis` | no/yes | none | refuse, stays `genesis` | A |
| `in_review` | no/yes | none | refuse, stays `in_review` | A — review-feedback text |
| `in_review` | either | valid non-empty | **succeed**, now `planned` (exit 0) | N/A (guard passes) |

## Non-goals (contract explicitly does NOT change)

- The four feedback-field allow/deny checks.
- The `_GUARDS` tuple order/identity.
- `wp_state.py` allow/deny (`allowed_targets`, force override) and
  `fsm_parity_baseline.jsonl`.
- Legalizing `blocked → planned` (explicitly declined, decision `01M2Q4F897ANB84HA6EHA9DG98`).
