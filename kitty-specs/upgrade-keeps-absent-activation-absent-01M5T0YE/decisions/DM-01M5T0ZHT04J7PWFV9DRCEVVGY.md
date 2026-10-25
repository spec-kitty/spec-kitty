# Decision Moment `01M5T0ZHT04J7PWFV9DRCEVVGY`

- **Mission:** `upgrade-keeps-absent-activation-absent-01M5T0YE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.fix-shape`
- **Input key:** `fix_shape`
- **Status:** `resolved`
- **Created:** `2026-10-25T17:15:53.537017+00:00`
- **Resolved:** `2026-10-25T17:16:02.119006+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which fix shape: leave an absent key absent at upgrade (successor migration), or record provenance for seeded entries in the activation ledger?

## Options

- successor migration leaves absent key absent
- seeded-provenance marker in activation.yaml
- Other

## Final answer

successor migration leaves absent key absent (issue #6629 fix shape 1). Chosen by the semi-auto runner under the operator's fix-now ruling: a provenance key would be refused by the activation ledger's L1 validation (unknown non-deny key fails closed, also on older rc8 CLIs) and could not be backfilled for already-seeded projects; recorded as an operator question in the PR.

## Rationale

_(none)_

## Change log

- `2026-10-25T17:15:53.537017+00:00` — opened
- `2026-10-25T17:16:02.119006+00:00` — resolved (final_answer="successor migration leaves absent key absent (issue #6629 fix shape 1). Chosen by the semi-auto runner under the operator's fix-now ruling: a provenance key would be refused by the activation ledger's L1 validation (unknown non-deny key fails closed, also on older rc8 CLIs) and could not be backfilled for already-seeded projects; recorded as an operator question in the PR.")
