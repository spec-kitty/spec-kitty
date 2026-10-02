# Decision Moment `01M3V5BPDBB9WG0KYY9Q4FVY58`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.legacy-ledger`
- **Input key:** `legacy_ledger`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:20:16.555580+00:00`
- **Resolved:** `2026-10-01T07:20:18.529871+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How do pre-fix Missions whose decision ledger was committed only on the coordination branch keep their decisions?

## Options

_(none)_

## Final answer

Fix-forward via doctor only: no read fallback. doctor decisions detects a ledger present only on the coordination branch and --repair copies it to the PRIMARY partition; teardown must not destroy such ledger content before it is repaired.

## Rationale

_(none)_

## Change log

- `2026-10-01T07:20:16.555580+00:00` — opened
- `2026-10-01T07:20:18.529871+00:00` — resolved (final_answer="Fix-forward via doctor only: no read fallback. doctor decisions detects a ledger present only on the coordination branch and --repair copies it to the PRIMARY partition; teardown must not destroy such ledger content before it is repaired.")
