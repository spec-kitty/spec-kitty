# Decision Moment `01M3M4GTA4ENB73A0HDS65WZ1P`

- **Mission:** `owned-checkout-lifecycle-authority-01M3M2ZB`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.flagless-linked-checkout`
- **Input key:** `flagless_linked_checkout_policy`
- **Status:** `resolved`
- **Created:** `2026-09-28T13:50:54.788703+00:00`
- **Resolved:** `2026-09-28T13:50:57.465881+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What should flagless commands do when run inside a linked checkout once implicit cwd adoption is retired?

## Options

_(none)_

## Final answer

Validated auto-adoption: keep adopting the current linked checkout but only through the canonical ownership validator; repository root checkout, lane and coordination worktrees keep today's behaviour; amend ADR 2026-08-12-1.

## Rationale

_(none)_

## Change log

- `2026-09-28T13:50:54.788703+00:00` — opened
- `2026-09-28T13:50:57.465881+00:00` — resolved (final_answer="Validated auto-adoption: keep adopting the current linked checkout but only through the canonical ownership validator; repository root checkout, lane and coordination worktrees keep today's behaviour; amend ADR 2026-08-12-1.")
