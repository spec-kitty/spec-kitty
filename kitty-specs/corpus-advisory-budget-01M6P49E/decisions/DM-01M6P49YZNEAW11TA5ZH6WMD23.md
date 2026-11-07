# Decision Moment `01M6P49YZNEAW11TA5ZH6WMD23`

- **Mission:** `corpus-advisory-budget-01M6P49E`
- **Origin flow:** `specify`
- **Slot key:** `specify.budget.approach`
- **Input key:** `budget_approach`
- **Status:** `resolved`
- **Created:** `2026-11-05T15:12:44.533815+00:00`
- **Resolved:** `2026-11-05T15:12:47.782850+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Acceptance is p95 <= 75% of timeout-minutes over a week of main and PR runs. Measurement: p95 20.3 min (102% of the 20-min cap), with ~11.5 min of the ~19.5 min run spent on fixed costs (whole-tree pytest collection, serial wall-clock policy scan) that two pinned guards forbid narrowing. Confirm the approach: derive the cap from the measured max with the repo's #5378 formula and make a budget expiry legible as INCOMPLETE (#4437), documenting why sharding is ruled out -- or shard the corpus selection by path and edit the two pinned guards?

## Options

- derive cap + legible expiry
- path shard

## Final answer

Derive the cap from measurement. Operator guidance (batch-11 D1 brief): measure first, do not just raise the number; a cancellation must not read as a failure. Measured: p95 20.3 min = 102% of the 20-min cap; fixed costs (whole-tree collection ~8 min, serial wall-clock policy scan ~3.5 min on PRs) are architectural -- tests/ci/test_corpus_blocking_home.py requires tree-wide corpus reach and tests/ci/test_contracts_routing.py requires exactly one pytest invocation, so a path shard would weaken the lane. Fix: record the measured max suite in the repo's #5378 headroom form, derive the cap with ceil((max+0:30)*1.5) = 31, extend the cap guard to enforce it for this job, and make a budget expiry read as INCOMPLETE-advisory rather than a failed test (#4437). Selection semantics, deselects, continue-on-error and trigger stay unchanged.

## Rationale

_(none)_

## Change log

- `2026-11-05T15:12:44.533815+00:00` — opened
- `2026-11-05T15:12:47.782850+00:00` — resolved (final_answer="Derive the cap from measurement. Operator guidance (batch-11 D1 brief): measure first, do not just raise the number; a cancellation must not read as a failure. Measured: p95 20.3 min = 102% of the 20-min cap; fixed costs (whole-tree collection ~8 min, serial wall-clock policy scan ~3.5 min on PRs) are architectural -- tests/ci/test_corpus_blocking_home.py requires tree-wide corpus reach and tests/ci/test_contracts_routing.py requires exactly one pytest invocation, so a path shard would weaken the lane. Fix: record the measured max suite in the repo's #5378 headroom form, derive the cap with ceil((max+0:30)*1.5) = 31, extend the cap guard to enforce it for this job, and make a budget expiry read as INCOMPLETE-advisory rather than a failed test (#4437). Selection semantics, deselects, continue-on-error and trigger stay unchanged.")
