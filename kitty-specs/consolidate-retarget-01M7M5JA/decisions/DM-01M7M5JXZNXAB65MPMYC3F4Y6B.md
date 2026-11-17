# Decision Moment `01M7M5JXZNXAB65MPMYC3F4Y6B`

- **Mission:** `consolidate-retarget-01M7M5JA`
- **Origin flow:** `specify`
- **Slot key:** `specify.retarget.rollback`
- **Input key:** `retarget_rollback`
- **Status:** `resolved`
- **Created:** `2026-11-17T07:12:19.957914+00:00`
- **Resolved:** `2026-11-17T07:46:10.313078+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How do --resume, --abort and the rollback authority treat a retargeted run?

## Options

- persist retarget in run record; one rollback authority restores; resume honours; ADR amendment (rec)
- Other

## Final answer

Operator ruling 2026-11-17 (relayed by core triager): retarget persisted in ConsolidationState; the one rollback authority restores it; --resume honours it and never re-commits; ADR 2026-09-19-1 amendment.

## Rationale

_(none)_

## Change log

- `2026-11-17T07:12:19.957914+00:00` - opened
- `2026-11-17T07:46:10.313078+00:00` - resolved (final_answer="Operator ruling 2026-11-17 (relayed by core triager): retarget persisted in ConsolidationState; the one rollback authority restores it; --resume honours it and never re-commits; ADR 2026-09-19-1 amendment.")
