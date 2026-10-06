# Decision Moment `01M48HBJR8J78X2WW4H5HW2J9S`

- **Mission:** `retire-runtime-bridge-delegates-01M48H5E`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.bulk-edit-classification`
- **Input key:** `bulk_edit`
- **Status:** `resolved`
- **Created:** `2026-10-06T12:00:03.336881+00:00`
- **Resolved:** `2026-10-06T12:00:06.514672+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Is this mission a bulk edit (change_mode: bulk_edit with an occurrence map)?

## Options

- No: per-site semantic refactor with call-path review
- Yes
- Other

## Final answer

No. Each repoint needs call-path judgement (which binding the code under test looks up), adapters need behaviour preservation, and mechanism-only tests are deleted rather than renamed. A uniform string rename would be wrong at many sites; the acceptance gate test (static scan) is the guardrail instead of an occurrence map.

## Rationale

_(none)_

## Change log

- `2026-10-06T12:00:03.336881+00:00` — opened
- `2026-10-06T12:00:06.514672+00:00` — resolved (final_answer="No. Each repoint needs call-path judgement (which binding the code under test looks up), adapters need behaviour preservation, and mechanism-only tests are deleted rather than renamed. A uniform string rename would be wrong at many sites; the acceptance gate test (static scan) is the guardrail instead of an occurrence map.")
