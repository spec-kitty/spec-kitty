# Decision Moment `01M3FGHBAEFWKC57MN4RRPEXB1`

- **Mission:** `hosted-opt-in-drain-ledger-01M3FFEV`
- **Origin flow:** `plan`
- **Slot key:** `plan.migration.implicit-default-sessions`
- **Input key:** `implicit_default_sessions`
- **Status:** `resolved`
- **Created:** `2026-09-26T18:44:42.958760+00:00`
- **Resolved:** `2026-09-26T18:44:45.665679+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the upgrade treat machines logged in against the implicit packaged default?

## Options

_(none)_

## Final answer

Backfill: the migration writes [sync].server_url from the stored session issuer_url when no endpoint is configured; a prior login counts as explicit opt-in. Drain stays off.

## Rationale

_(none)_

## Change log

- `2026-09-26T18:44:42.958760+00:00` — opened
- `2026-09-26T18:44:45.665679+00:00` — resolved (final_answer="Backfill: the migration writes [sync].server_url from the stored session issuer_url when no endpoint is configured; a prior login counts as explicit opt-in. Drain stays off.")
