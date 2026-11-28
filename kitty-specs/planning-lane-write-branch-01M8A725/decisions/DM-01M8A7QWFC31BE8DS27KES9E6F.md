# Decision Moment `01M8A7QWFC31BE8DS27KES9E6F`

- **Mission:** `planning-lane-write-branch-01M8A725`
- **Origin flow:** `plan`
- **Slot key:** `plan.evidence.window-start`
- **Input key:** `planning_window_start`
- **Status:** `resolved`
- **Created:** `2026-11-25T20:53:16.908354+00:00`
- **Resolved:** `2026-11-25T21:13:46.382760+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does a default Mission's planning evidence window start (FR-010)?

## Options

- The commit on the Mission branch that introduced the WP window-opening status event (durable, same derivation as the review range Q10/Q12)
- The clone-local claim-base ref
- Move the planning pin onto the Mission branch
- Other

## Final answer

The commit on the Mission branch that introduced the WP window-opening status event (its claim). Source: operator ruling 2026-11-25 on #7860; engineering alignment confirmed; 5 WPs.

## Rationale

_(none)_

## Change log

- `2026-11-25T20:53:16.908354+00:00` - opened
- `2026-11-25T21:13:46.382760+00:00` - resolved (final_answer="The commit on the Mission branch that introduced the WP window-opening status event (its claim). Source: operator ruling 2026-11-25 on #7860; engineering alignment confirmed; 5 WPs.")
