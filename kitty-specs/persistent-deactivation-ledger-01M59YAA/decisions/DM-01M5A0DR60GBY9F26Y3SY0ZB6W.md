# Decision Moment `01M5A0DR60GBY9F26Y3SY0ZB6W`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `plan`
- **Slot key:** `plan.cascade.walk_through_denied`
- **Input key:** `cascade_walk_through_denied`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:58:19.328680+00:00`
- **Resolved:** `2026-10-19T11:58:22.936800+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Does a cascade activation walk continue through a deactivated node to its children?

## Options

_(none)_

## Final answer

Stop at the denied node: nothing reachable only through it is activated; children reachable over another non-excluded path still are; --include-deactivated restores the full walk.

## Rationale

_(none)_

## Change log

- `2026-10-19T11:58:19.328680+00:00` — opened
- `2026-10-19T11:58:22.936800+00:00` — resolved (final_answer="Stop at the denied node: nothing reachable only through it is activated; children reachable over another non-excluded path still are; --include-deactivated restores the full walk.")
