# Decision Moment `01M5HS6C9YQV3WR0HHDN5XS13Z`

- **Mission:** `event-write-hygiene-01M5HS55`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.test-seeds`
- **Input key:** `test_seed_handling`
- **Status:** `resolved`
- **Created:** `2026-10-22T12:25:53.214512+00:00`
- **Resolved:** `2026-10-22T12:25:56.177790+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How are the ~195 test files seeding via store.append_event handled?

## Options

- Codemod in this PR
- Split into a follow-up

## Final answer

Codemod in this PR onto a tests/_support atomic seeding helper.

## Rationale

_(none)_

## Change log

- `2026-10-22T12:25:53.214512+00:00` — opened
- `2026-10-22T12:25:56.177790+00:00` — resolved (final_answer="Codemod in this PR onto a tests/_support atomic seeding helper.")
