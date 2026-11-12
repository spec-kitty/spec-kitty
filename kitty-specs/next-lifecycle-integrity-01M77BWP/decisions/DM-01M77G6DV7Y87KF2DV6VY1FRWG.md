# Decision Moment `01M77G6DV7Y87KF2DV6VY1FRWG`

- **Mission:** `next-lifecycle-integrity-01M77BWP`
- **Origin flow:** `plan`
- **Slot key:** `plan.next.query_invariant`
- **Input key:** `plan.next.query_invariant`
- **Status:** `resolved`
- **Created:** `2026-11-12T09:07:36.935374+00:00`
- **Resolved:** `2026-11-12T09:07:39.096542+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

FR-010 invariant restatement

## Options

- question iff decision_id
- keep options required

## Final answer

question iff decision_id

## Rationale

Operator ruling 2026-11-12: question non-null iff decision_id non-null; when set, options or input_key present. Enforce by construction: split the pending-decision fields into a validated value object so invalid envelopes cannot be created.

## Change log

- `2026-11-12T09:07:36.935374+00:00` - opened
- `2026-11-12T09:07:39.096542+00:00` - resolved (final_answer="question iff decision_id")
