# Decision Moment `01M3VCS2H5R6R04BCD41RN8GFD`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.ledger-committers`
- **Input key:** `ledger_committers`
- **Status:** `resolved`
- **Created:** `2026-10-01T09:29:54.981420+00:00`
- **Resolved:** `2026-10-01T09:29:56.888966+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which existing PRIMARY-partition commands commit a new Mission's decision ledger (FR-009b)?

## Options

_(none)_

## Final answer

spec-commit and accept only (narrowed from spec-commit/setup-plan/finalize-tasks/accept): those are the existing committers that already commit the ledger once it is PRIMARY (WP12/WP16); setup-plan and finalize-tasks keep committing only their own artefacts, so no new auto-commit is added. Analyze finding G1.

## Rationale

_(none)_

## Change log

- `2026-10-01T09:29:54.981420+00:00` — opened
- `2026-10-01T09:29:56.888966+00:00` — resolved (final_answer="spec-commit and accept only (narrowed from spec-commit/setup-plan/finalize-tasks/accept): those are the existing committers that already commit the ledger once it is PRIMARY (WP12/WP16); setup-plan and finalize-tasks keep committing only their own artefacts, so no new auto-commit is added. Analyze finding G1.")
