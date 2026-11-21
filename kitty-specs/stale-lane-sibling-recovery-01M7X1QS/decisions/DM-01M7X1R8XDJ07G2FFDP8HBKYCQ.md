# Decision Moment `01M7X1R8XDJ07G2FFDP8HBKYCQ`

- **Mission:** `stale-lane-sibling-recovery-01M7X1QS`
- **Origin flow:** `specify`
- **Slot key:** `specify.scenario.primary`
- **Input key:** `primary_scenario`
- **Status:** `resolved`
- **Created:** `2026-11-20T17:58:30.573746+00:00`
- **Resolved:** `2026-11-20T17:58:33.414353+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Who hits the stale refusal, when, and what must happen next?

## Options

_(none)_

## Final answer

Answered from #7755/#7754 (unattended scheduled run): the operator running spec-kitty consolidate on a lanes Mission whose approved lanes edit the same file; the in-run auto-rebase of the later lane stops on a conflict with a sibling lane consolidated earlier in that run; the rollback then restores the Mission branch. The refusal must say the auto-rebase stopped and why, name the sibling lane branch (it survives rollback), and give a remedy that works for an approved WP; after the operator follows it, the next run must pass the lane.

## Rationale

_(none)_

## Change log

- `2026-11-20T17:58:30.573746+00:00` - opened
- `2026-11-20T17:58:33.414353+00:00` - resolved (final_answer="Answered from #7755/#7754 (unattended scheduled run): the operator running spec-kitty consolidate on a lanes Mission whose approved lanes edit the same file; the in-run auto-rebase of the later lane stops on a conflict with a sibling lane consolidated earlier in that run; the rollback then restores the Mission branch. The refusal must say the auto-rebase stopped and why, name the sibling lane branch (it survives rollback), and give a remedy that works for an approved WP; after the operator follows it, the next run must pass the lane.")
