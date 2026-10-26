# Decision Moment `01M5X498X3ATTAB12KQWMDPZRV`

- **Mission:** `issue-matrix-terminality-all-rows-01M5X1ZJ`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.absent-matrix-probe`
- **Input key:** `absent_matrix_probe`
- **Status:** `resolved`
- **Created:** `2026-10-26T22:11:21.123973+00:00`
- **Resolved:** `2026-10-26T22:14:26.754250+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where should 'matrix file absent at a valid ref' be told apart from a failed probe: a new typed code (ISSUE_MATRIX_NOT_AUTHORED) on the existing mission_runtime reader read_issue_matrix_ref_content, or a separate presence function?

## Options

- New typed code on the existing reader
- Separate presence function
- Other

## Final answer

New typed code on the existing reader (ISSUE_MATRIX_NOT_AUTHORED)

## Rationale

_(none)_

## Change log

- `2026-10-26T22:11:21.123973+00:00` — opened
- `2026-10-26T22:14:26.754250+00:00` — resolved (final_answer="New typed code on the existing reader (ISSUE_MATRIX_NOT_AUTHORED)")
