# Decision Moment `01M3TZHMR2CVAY2FNHSGNJJYSR`

- **Mission:** `ci-runtime-stabilisation-01M3TZH6`
- **Origin flow:** `specify`
- **Slot key:** `specify.ci.ready-for-review`
- **Input key:** `ready_for_review_rerun`
- **Status:** `resolved`
- **Created:** `2026-10-01T05:38:40.002046+00:00`
- **Resolved:** `2026-10-01T05:38:41.571561+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

ready_for_review re-runs full CI on an already-green SHA (~1,210 runner-min/day). How to handle?

## Options

- Skip-if-green guard
- Drop the trigger type
- Leave as is
- Other

## Final answer

Skip-if-green guard

## Rationale

_(none)_

## Change log

- `2026-10-01T05:38:40.002046+00:00` — opened
- `2026-10-01T05:38:41.571561+00:00` — resolved (final_answer="Skip-if-green guard")
