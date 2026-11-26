# Decision Moment `01M88RZ308V571DYGPKD17ZWDA`

- **Mission:** `approved-lane-resolution-route-01M7WW0Z`
- **Origin flow:** `plan`
- **Slot key:** `plan.rebase.main-drift`
- **Input key:** `rebase_on_main`
- **Status:** `resolved`
- **Created:** `2026-11-25T07:15:49.896875+00:00`
- **Resolved:** `2026-11-25T07:15:55.033516+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Main moved 194 commits under the Mission (incl. #7754/#7755 fixes, #7802 approved_bound, CONTRACT_VERSION 1.30.0). Rebase or merge, and when?

## Options

_(none)_

## Final answer

REBASE (never merge main in, #7749), timing (a) now: WP07 must reuse main's SiblingLane helpers and WP05 builds on main's #7802 approved_bound changes, so building on the old base would cost a second conflict round and double re-review. Approved lanes get delta re-reviews and re-approval. Force-with-lease authorized for this Mission's lane, coordination and topic branches only. WP09 bumps CONTRACT_VERSION to 1.31.0. (operator, 2026-11-25)

## Rationale

_(none)_

## Change log

- `2026-11-25T07:15:49.896875+00:00` - opened
- `2026-11-25T07:15:55.033516+00:00` - resolved (final_answer="REBASE (never merge main in, #7749), timing (a) now: WP07 must reuse main's SiblingLane helpers and WP05 builds on main's #7802 approved_bound changes, so building on the old base would cost a second conflict round and double re-review. Approved lanes get delta re-reviews and re-approval. Force-with-lease authorized for this Mission's lane, coordination and topic branches only. WP09 bumps CONTRACT_VERSION to 1.31.0. (operator, 2026-11-25)")
