# Decision Moment `01M5T0VPQ9FD9CD7G846CPQGX5`

- **Mission:** `eventbridge-gate-and-locked-appends-01M5T0TN`
- **Origin flow:** `specify`
- **Slot key:** `specify.appends.op-records`
- **Input key:** `op_record_appends`
- **Status:** `resolved`
- **Created:** `2026-10-25T17:13:47.497804+00:00`
- **Resolved:** `2026-10-25T17:13:51.770509+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Do the kitty-ops Op-record appends in invocation/writer.py (ops-index, op-closures, <ULID>.jsonl), which G-5 does not list, take the same lock?

## Options

- Yes, every unlocked append
- No, only the eight G-5 sites
- Other

## Final answer

Yes, every unlocked append. Operator ruling 2026-10-25 (#6117 decision 3, mission brief): the interim ledger lock extends to every unlocked append now, giving one lock contract. #6564 (Op-record placement) is merged, so the coordination point is settled.

## Rationale

_(none)_

## Change log

- `2026-10-25T17:13:47.497804+00:00` — opened
- `2026-10-25T17:13:51.770509+00:00` — resolved (final_answer="Yes, every unlocked append. Operator ruling 2026-10-25 (#6117 decision 3, mission brief): the interim ledger lock extends to every unlocked append now, giving one lock contract. #6564 (Op-record placement) is merged, so the coordination point is settled.")
