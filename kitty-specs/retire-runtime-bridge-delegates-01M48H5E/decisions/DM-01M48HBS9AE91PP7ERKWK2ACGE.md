# Decision Moment `01M48HBS9AE91PP7ERKWK2ACGE`

- **Mission:** `retire-runtime-bridge-delegates-01M48H5E`
- **Origin flow:** `plan`
- **Slot key:** `plan.design.acceptance-gate`
- **Input key:** `acceptance_gate`
- **Status:** `resolved`
- **Created:** `2026-10-06T12:00:10.026065+00:00`
- **Resolved:** `2026-10-06T12:00:13.216190+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is red-first ATDD done for a deletion refactor?

## Options

- Static acceptance test per seam, strict-xfail until that seam is done, plus adapter characterisation tests
- Only behaviour tests
- Other

## Final answer

A static acceptance test parametrized per seam (no delegate definitions in the bridge, no _rb back-edges to delegated names, re-export identity) lands first; seams not yet migrated are xfail(strict=True) and each seam WP removes its own xfail. Adapter characterisation tests land first and stay green throughout.

## Rationale

_(none)_

## Change log

- `2026-10-06T12:00:10.026065+00:00` — opened
- `2026-10-06T12:00:13.216190+00:00` — resolved (final_answer="A static acceptance test parametrized per seam (no delegate definitions in the bridge, no _rb back-edges to delegated names, re-export identity) lands first; seams not yet migrated are xfail(strict=True) and each seam WP removes its own xfail. Adapter characterisation tests land first and stay green throughout.")
