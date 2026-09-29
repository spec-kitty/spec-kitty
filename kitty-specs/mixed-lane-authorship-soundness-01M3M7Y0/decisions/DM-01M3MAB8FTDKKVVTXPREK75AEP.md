# Decision Moment `01M3MAB8FTDKKVVTXPREK75AEP`

- **Mission:** `mixed-lane-authorship-soundness-01M3M7Y0`
- **Origin flow:** `plan`
- **Slot key:** `plan.gate.refuse-rollback`
- **Input key:** `refuse_rollback`
- **Status:** `resolved`
- **Created:** `2026-09-28T15:32:44.154636+00:00`
- **Resolved:** `2026-09-28T15:32:46.967147+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

A reconciliation REFUSE does not restore the target today (only FAIL rolls back). How should the mission handle it?

## Options

- Both: pre-mutation abort + rollback
- Rollback on REFUSE only
- Scope to new refusals
- Other

## Final answer

Rollback on REFUSE only: every post-advance REFUSE gets the same CAS rollback as FAIL; no new pre-mutation exit.

## Rationale

_(none)_

## Change log

- `2026-09-28T15:32:44.154636+00:00` — opened
- `2026-09-28T15:32:46.967147+00:00` — resolved (final_answer="Rollback on REFUSE only: every post-advance REFUSE gets the same CAS rollback as FAIL; no new pre-mutation exit.")
