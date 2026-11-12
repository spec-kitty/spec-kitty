# Data model: next lifecycle integrity

updated: 2026-11-12. Revised after the post-tasks squad and the operator rulings.

## FinishedBoardVerdict (pure, `runtime_bridge_cores`)

`finished_board_verdict(board_step, *, accepted_at, latest_transition_at)`

| Value | When | Advancing `next` (gate applies) | Query `next_command` |
|---|---|---|---|
| `NONE` | The board step is not `accept`/`done` | See the never-rewind table | Advance command |
| `AWAITING_ACCEPTANCE` | The board step is `accept`/`done`, and `accepted_at` is missing, unparsable, or not later than `latest_transition_at` | `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE` | `spec-kitty accept --mission <handle>` |
| `ACCEPTED` | The board step is `accept`/`done`, and `accepted_at` is later than the board's latest WP transition | `kind=terminal` | `spec-kitty consolidate --mission <handle>` |

- A finished board has acceptable endings for every WP: approved, done, or canceled.
- Landed Missions are answered earlier by the merged short-circuit (`terminal`, no `next_command`).

## Never-rewind gate (advancing `next`)

The gate applies when all three hold:
- `mission_type == software-dev`;
- the board is finalized (the board step is not None);
- the run is **not authoritative**: there is no run, the run is untouched, or its issued step is a planning step before analyze.

A run whose issued step is analyze, implement, review or accept is authoritative. A `RunStateMissing` falls through to the existing loader error.

| Board step | Answer |
|---|---|
| `accept` / `done` | the verdict row above |
| `implement` / `review`, dispatchable | widened front phase dispatches from the board (any `--result`) |
| `implement` / `review`, not dispatchable (WP in progress or claimed) | `kind=blocked`, `error_code=BOARD_STEP_NOT_DISPATCHABLE`, WP named, `next_command` = resume command |
| `blocked:*` | existing board blocked decision |

A gate answer sets `suppress_step_pairing`: `next_cmd` does not pair the previous `started` record.

## Decision envelope additions

- `next_command: str | None`. Additive; it appears in `to_dict` only when set.
- `suppress_step_pairing: bool`. Internal only; never serialized.
- `PendingDecisionPrompt(decision_id, question, input_key, options)` is a validated value object.

Construction invariant for `query` and `decision_required`:
- `question` is non-null ⇔ `decision_id` is non-null;
- when they are set, `options` or `input_key` is present.

## rollback_reset (status event `policy_metadata`, PLANNED hop)

```json
{"rollback_reset": {"scope": "full" | "narrowed",
                     "reset": ["T001", "T002"],
                     "previously_completed": ["T001"],
                     "reason": "<operator --note/--reason, or the derived rollback reason>"}}
```

Invariants:
- `reset` ⊆ roster;
- `skipped` subtasks are never in `reset`, and naming one in `--reset-subtasks` is refused;
- `previously_completed` ⊆ `reset`;
- `scope == "narrowed"` ⇒ an operator reason is present;
- the record merges with `lane_head` and `wp_window`; it never replaces them.
