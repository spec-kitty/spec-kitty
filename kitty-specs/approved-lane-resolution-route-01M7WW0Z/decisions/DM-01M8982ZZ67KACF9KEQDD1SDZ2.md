# Decision Moment `01M8982ZZ67KACF9KEQDD1SDZ2`

- **Mission:** `approved-lane-resolution-route-01M7WW0Z`
- **Origin flow:** `plan`
- **Slot key:** `plan.wp08.review-window-semantics`
- **Input key:** `review_window_contested_scope`
- **Status:** `resolved`
- **Created:** `2026-11-25T11:40:06.502736+00:00`
- **Resolved:** `2026-11-25T11:40:11.522115+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Should an approved commit that lies only inside a canceled WP's review window (refused as CONTESTED_COMMIT) be re-ruled in this Mission?

## Options

_(none)_

## Final answer

OUT of this Mission. #5604 keeps today's semantics (CONTESTED refuses; --attest-canceled-superseded lifts it). The dispatcher files a separate issue. (operator, 2026-11-25)

## Rationale

_(none)_

## Change log

- `2026-11-25T11:40:06.502736+00:00` - opened
- `2026-11-25T11:40:11.522115+00:00` - resolved (final_answer="OUT of this Mission. #5604 keeps today's semantics (CONTESTED refuses; --attest-canceled-superseded lifts it). The dispatcher files a separate issue. (operator, 2026-11-25)")
