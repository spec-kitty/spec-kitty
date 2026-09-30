# Decision Moment `01M3M4GMJVYEGW80YJEA7CNWGF`

- **Mission:** `owned-checkout-lifecycle-authority-01M3M2ZB`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.owned-coord-next`
- **Input key:** `owned_coord_next_policy`
- **Status:** `resolved`
- **Created:** `2026-09-28T13:50:48.923878+00:00`
- **Resolved:** `2026-09-28T13:50:51.927014+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Owned next on coordination topologies (lanes_with_coord): keep or refuse?

## Options

_(none)_

## Final answer

Keep + harden: single minter records topology; each command enforces its allowed topologies (ADR 2026-09-03-1 lifecycle commands single_branch-only); FR-011 hardens the coordination probe with deterministic fault injection.

## Rationale

_(none)_

## Change log

- `2026-09-28T13:50:48.923878+00:00` — opened
- `2026-09-28T13:50:51.927014+00:00` — resolved (final_answer="Keep + harden: single minter records topology; each command enforces its allowed topologies (ADR 2026-09-03-1 lifecycle commands single_branch-only); FR-011 hardens the coordination probe with deterministic fault injection.")
