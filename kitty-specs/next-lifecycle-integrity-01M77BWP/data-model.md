# Data model: next lifecycle integrity

## FinishedBoardVerdict (pure, `runtime_bridge_cores`)
| Value | When | Advancing `next` | Query `next_command` |
|---|---|---|---|
| `NONE` | The board step is not `accept`/`done` (or there are no WPs / no finalized board) | Existing path | Advance command |
| `AWAITING_ACCEPTANCE` | The board step is `accept`/`done` and the Mission is not accepted | `kind=blocked`, `error_code=MISSION_AWAITING_ACCEPTANCE` | `spec-kitty accept --mission <handle>` |
| `ACCEPTED` | The board step is `accept`/`done` and `accepted_at` is set | `kind=terminal` | `spec-kitty consolidate --mission <handle>` |

Landed Missions are answered earlier by the existing merged short-circuit (`terminal`, with no `next_command`).

**Invariant:** the verdict is a function of `(board_step, accepted)` only. Acceptance never counts unless the board is finished.

## Gate applicability (advance only)
`gate_applies = verdict != NONE and (run is None or run.issued_step_id not in {implement, review, accept})`

## Decision envelope additions
- `next_command: str | None`. It is additive and appears in `to_dict` only when set.
- Query invariant: `question is not None` ⇔ `decision_id is not None and options is not None`.

## rollback_reset (status event `policy_metadata`, PLANNED hop)
```json
{"rollback_reset": {"scope": "full" | "narrowed",
                     "reset": ["T001", "T002"],
                     "previously_completed": ["T001"],
                     "reason": "<operator --note/--reason, or the derived rollback reason>"}}
```

**Invariants:**
- `reset` ⊆ roster.
- `skipped` subtasks are never in `reset`.
- `previously_completed` ⊆ `reset`.
- `scope == "narrowed"` ⇒ an operator reason is present.
