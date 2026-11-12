# Decision Moment `01M77G6HY4WX5PBGYQZJVFCFG2`

- **Mission:** `next-lifecycle-integrity-01M77BWP`
- **Origin flow:** `plan`
- **Slot key:** `plan.next.acceptance_freshness`
- **Input key:** `plan.next.acceptance_freshness`
- **Status:** `resolved`
- **Created:** `2026-11-12T09:07:41.124793+00:00`
- **Resolved:** `2026-11-12T09:07:43.456950+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

What counts as accepted?

## Options

- acceptance newer than board
- residual

## Final answer

acceptance newer than board

## Rationale

Operator ruling 2026-11-12: accepted only when accepted_at is later than the board's latest WP transition (same single status read); a re-approval after reopen requires acceptance again.

## Change log

- `2026-11-12T09:07:41.124793+00:00` - opened
- `2026-11-12T09:07:43.456950+00:00` - resolved (final_answer="acceptance newer than board")
