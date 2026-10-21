# Decision Moment `01M5BNZRMPZSM6V7S82YE3D5MN`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `plan`
- **Slot key:** `plan.cascade.mission_type_source`
- **Input key:** `mission_type_cascade_source`
- **Status:** `resolved`
- **Created:** `2026-10-20T03:34:24.150314+00:00`
- **Resolved:** `2026-10-20T03:34:28.636821+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

charter activate mission-type X --cascade is a pre-existing no-op (mission type is not a cascade source). How to handle?

## Options

_(none)_

## Final answer

Make mission type a cascade source: a new WP makes charter activate mission-type X --cascade walk the mission type's contracts and referenced artifacts with the same skip/report and stop-at-deny rules.

## Rationale

_(none)_

## Change log

- `2026-10-20T03:34:24.150314+00:00` — opened
- `2026-10-20T03:34:28.636821+00:00` — resolved (final_answer="Make mission type a cascade source: a new WP makes charter activate mission-type X --cascade walk the mission type's contracts and referenced artifacts with the same skip/report and stop-at-deny rules.")
