# Decision Moment `01M490FB62VCMW1T35FQ6T5M4T`

- **Mission:** `runtime-bridge-query-seam-01M490EQ`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.boundary`
- **Input key:** `scope_boundary`
- **Status:** `resolved`
- **Created:** `2026-10-06T16:24:15.298973+00:00`
- **Resolved:** `2026-10-06T16:24:26.868701+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What is the mission boundary: which runtime_bridge clusters move, and what stays out?

## Options

- query+answer+shared mapping seam only (operator brief)
- also #2562 engine dedup
- Other

## Final answer

query+answer+shared mapping seam only (operator brief): move the query/answer cluster and the decision-mapping helpers it shares with the decide path; #2562 (engine run-advance dedup, significance/RACI gap, provide_decision_answer noqa) stays out; stay inside src/runtime/next and its tests

## Rationale

_(none)_

## Change log

- `2026-10-06T16:24:15.298973+00:00` — opened
- `2026-10-06T16:24:26.868701+00:00` — resolved (final_answer="query+answer+shared mapping seam only (operator brief): move the query/answer cluster and the decision-mapping helpers it shares with the decide path; #2562 (engine run-advance dedup, significance/RACI gap, provide_decision_answer noqa) stays out; stay inside src/runtime/next and its tests")
