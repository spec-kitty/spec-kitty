# Decision Moment `01M3BGRBWBDWG3F3EEA4Z5S8VQ`

- **Mission:** `advancing-next-board-unification-01M3BGQ0`
- **Origin flow:** `specify`
- **Slot key:** `specify.behavior.advance-contract`
- **Input key:** `advance_contract`
- **Status:** `resolved`
- **Created:** `2026-09-25T05:31:35.179544+00:00`
- **Resolved:** `2026-09-25T05:36:27.647093+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

On a rejection/coord path where advancing next currently no-ops or blocks, what is the required success contract: re-dispatch the actionable WP (agree with query mode) with a blocked+recovery floor only when no WP is actionable?

## Options

- Re-dispatch actionable WP; blocked+recovery only when none actionable
- Always blocked+recovery (never auto re-dispatch)
- Other

## Final answer

Advancing next must agree with query mode: dispatch the actionable WP (e.g. implement WP01 for a rejected WP that fell to planned, or a coord WP the primary dir cannot see); return kind=blocked with a named recovery command ONLY when the board has no actionable WP. Never emit the WP-less composition placeholder as a live advancing loop state.

## Rationale

_(none)_

## Change log

- `2026-09-25T05:31:35.179544+00:00` — opened
- `2026-09-25T05:36:27.647093+00:00` — resolved (final_answer="Advancing next must agree with query mode: dispatch the actionable WP (e.g. implement WP01 for a rejected WP that fell to planned, or a coord WP the primary dir cannot see); return kind=blocked with a named recovery command ONLY when the board has no actionable WP. Never emit the WP-less composition placeholder as a live advancing loop state.")
