# Decision Moment `01M7M5K221R8DE5KBNVX5BCPYW`

- **Mission:** `consolidate-retarget-01M7M5JA`
- **Origin flow:** `specify`
- **Slot key:** `specify.retarget.parity`
- **Input key:** `retarget_parity`
- **Status:** `resolved`
- **Created:** `2026-11-17T07:12:24.129265+00:00`
- **Resolved:** `2026-11-17T07:46:14.506949+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

--dry-run and orchestrator-api consolidate-mission parity?

## Options

- dry-run forecasts identically; orchestrator-api refuses retargets (no rollback door) (rec)
- orchestrator-api adds --retarget without rollback
- Other

## Final answer

Operator ruling 2026-11-17 (relayed by core triager): --dry-run forecasts the retarget with the same codes; orchestrator-api consolidate-mission refuses a retarget (no rollback door), no contract change.

## Rationale

_(none)_

## Change log

- `2026-11-17T07:12:24.129265+00:00` - opened
- `2026-11-17T07:46:14.506949+00:00` - resolved (final_answer="Operator ruling 2026-11-17 (relayed by core triager): --dry-run forecasts the retarget with the same codes; orchestrator-api consolidate-mission refuses a retarget (no rollback door), no contract change.")
