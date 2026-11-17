# Decision Moment `01M7M5JVWHNG5ZC6JD0S4CSJ5E`

- **Mission:** `consolidate-retarget-01M7M5JA`
- **Origin flow:** `specify`
- **Slot key:** `specify.retarget.record-timing`
- **Input key:** `retarget_record_timing`
- **Status:** `resolved`
- **Created:** `2026-11-17T07:12:17.809529+00:00`
- **Resolved:** `2026-11-17T07:46:08.052097+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When and where is meta.json target_branch rewritten?

## Options

- up front, first mutation, own commit with provenance on the new PRIMARY checkout (rec)
- inside the landing
- Other

## Final answer

Operator ruling 2026-11-17 (relayed by core triager): up front: in effect before the pre-mutation snapshot; meta.json target_branch rewrite committed as the first mutation inside the rollback door, with provenance {from,to,actor,at,reason}; --retarget-reason optional with a default.

## Rationale

_(none)_

## Change log

- `2026-11-17T07:12:17.809529+00:00` - opened
- `2026-11-17T07:46:08.052097+00:00` - resolved (final_answer="Operator ruling 2026-11-17 (relayed by core triager): up front: in effect before the pre-mutation snapshot; meta.json target_branch rewrite committed as the first mutation inside the rollback door, with provenance {from,to,actor,at,reason}; --retarget-reason optional with a default.")
