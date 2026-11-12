# Decision Moment `01M78JBFFCCN3VQJ88Z4QX1AFJ`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `specify`
- **Slot key:** `claimant_mismatch`
- **Input key:** `claimant_mismatch`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:04:34.028428+00:00`
- **Resolved:** `2026-11-12T19:04:36.117927+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

How is an approver differing from the in_review claimant handled (#7573)?

## Options

_(none)_

## Final answer

Refuse: an unforced in_review->approved must come from the in_review claimant; otherwise refuse with a new code whose remedy re-claims via agent action review <WP> --agent <id>. Forced moves stay possible and are recorded as forced, never as a review.

## Rationale

Operator ruling 2026-11-12 (recommended option).

## Change log

- `2026-11-12T19:04:34.028428+00:00` - opened
- `2026-11-12T19:04:36.117927+00:00` - resolved (final_answer="Refuse: an unforced in_review->approved must come from the in_review claimant; otherwise refuse with a new code whose remedy re-claims via agent action review <WP> --agent <id>. Forced moves stay possible and are recorded as forced, never as a review.")
