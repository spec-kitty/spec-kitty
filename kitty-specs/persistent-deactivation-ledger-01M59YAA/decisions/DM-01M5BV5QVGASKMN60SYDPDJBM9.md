# Decision Moment `01M5BV5QVGASKMN60SYDPDJBM9`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `plan`
- **Slot key:** `plan.contract.required_on_read`
- **Input key:** `required_always_active_divergence`
- **Status:** `resolved`
- **Created:** `2026-10-20T05:05:02.832680+00:00`
- **Resolved:** `2026-10-20T05:05:06.931892+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Should core treat required/locked artifacts as always active on read, like the charter service?

## Options

_(none)_

## Final answer

Log as a divergence (ADR + corpus), settle before the remote cutover; core keeps: required never subtracted by deny, not added under an explicit allow list.

## Rationale

_(none)_

## Change log

- `2026-10-20T05:05:02.832680+00:00` — opened
- `2026-10-20T05:05:06.931892+00:00` — resolved (final_answer="Log as a divergence (ADR + corpus), settle before the remote cutover; core keeps: required never subtracted by deny, not added under an explicit allow list.")
