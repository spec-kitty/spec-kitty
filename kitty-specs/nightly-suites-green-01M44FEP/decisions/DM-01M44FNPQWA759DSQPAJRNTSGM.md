# Decision Moment `01M44FNPQWA759DSQPAJRNTSGM`

- **Mission:** `nightly-suites-green-01M44FEP`
- **Origin flow:** `specify`
- **Slot key:** `specify.track-a.bare-slug-fix`
- **Input key:** `track_a_fix`
- **Status:** `resolved`
- **Created:** `2026-10-04T22:13:40.220824+00:00`
- **Resolved:** `2026-10-04T22:13:42.572671+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Bare-slug coordination Mission has two directory names and three classifiers keyed on one (#5651). Which fix?

## Options

- One directory name
- Alias authority
- Split Track A out

## Final answer

Alias authority: keep the composed coordination directory; one exact alias set {primary dir name, composed <slug>-<mid8>} consumed by the partition classifier, the bookkeeping exemption and the teardown metadata read. Edits _is_bookkeeping in consolidation/reconciliation.py (adjacent to #5668).

## Rationale

_(none)_

## Change log

- `2026-10-04T22:13:40.220824+00:00` — opened
- `2026-10-04T22:13:42.572671+00:00` — resolved (final_answer="Alias authority: keep the composed coordination directory; one exact alias set {primary dir name, composed <slug>-<mid8>} consumed by the partition classifier, the bookkeeping exemption and the teardown metadata read. Edits _is_bookkeeping in consolidation/reconciliation.py (adjacent to #5668).")
