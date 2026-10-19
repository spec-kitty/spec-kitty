# Decision Moment `01M5ANA053MTJF373PY0W9CXDV`

- **Mission:** `charter-tests-deep-roi-pass-01M5AN9J`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.deletion-bar`
- **Input key:** `deletion_bar`
- **Status:** `resolved`
- **Created:** `2026-10-19T18:03:16.515942+00:00`
- **Resolved:** `2026-10-19T18:04:53.296243+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How strict is the deletion bar: when a test is redundant, may we delete it only if a named test covers the same behaviour (strict), or also merge or parametrize near-duplicates into a surviving test (consolidate)? And must line coverage of src/charter stay unchanged?

## Options

- Strict: delete only with a named covering test; coverage of src/charter must not drop
- Consolidate: also merge/parametrize near-duplicates; coverage must not drop
- Other

## Final answer

Consolidate: delete with a named covering test, and also merge/parametrize near-duplicates into a surviving test; src/charter line coverage must not drop

## Rationale

_(none)_

## Change log

- `2026-10-19T18:03:16.515942+00:00` — opened
- `2026-10-19T18:04:53.296243+00:00` — resolved (final_answer="Consolidate: delete with a named covering test, and also merge/parametrize near-duplicates into a surviving test; src/charter line coverage must not drop")
