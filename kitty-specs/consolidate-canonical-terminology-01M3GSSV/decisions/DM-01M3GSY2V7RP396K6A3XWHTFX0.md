# Decision Moment `01M3GSY2V7RP396K6A3XWHTFX0`

- **Mission:** `consolidate-canonical-terminology-01M3GSSV`
- **Origin flow:** `specify`
- **Slot key:** `specify.deprecation.merge-alias-horizon`
- **Input key:** `merge_alias_horizon`
- **Status:** `resolved`
- **Created:** `2026-09-27T06:48:11.879659+00:00`
- **Resolved:** `2026-09-27T06:51:57.723295+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

How long should 'spec-kitty merge' survive as a deprecated warning-emitting alias?

## Options

- until-next-major
- one-release-then-remove
- indefinite
- Other

## Final answer

Remove 'spec-kitty merge' now as a clean rename in the 4.x rc cycle (no back-compat working alias); leave a hidden stub that exits with a 'renamed to consolidate' migration error. NOTE: overrides issue #3080 AC which mandated a deprecated alias — justified by pre-stable 4.0.0rc timing.

## Rationale

_(none)_

## Change log

- `2026-09-27T06:48:11.879659+00:00` — opened
- `2026-09-27T06:51:57.723295+00:00` — resolved (final_answer="Remove 'spec-kitty merge' now as a clean rename in the 4.x rc cycle (no back-compat working alias); leave a hidden stub that exits with a 'renamed to consolidate' migration error. NOTE: overrides issue #3080 AC which mandated a deprecated alias — justified by pre-stable 4.0.0rc timing.")
