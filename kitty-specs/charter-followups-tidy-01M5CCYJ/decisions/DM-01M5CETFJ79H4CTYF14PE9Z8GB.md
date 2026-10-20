# Decision Moment `01M5CETFJ79H4CTYF14PE9Z8GB`

- **Mission:** `charter-followups-tidy-01M5CCYJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.migrations.ledger-drift`
- **Input key:** `migration_flag_ledger_drift`
- **Status:** `resolved`
- **Created:** `2026-10-20T10:48:25.415474+00:00`
- **Resolved:** `2026-10-20T10:48:28.662900+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#6539: declaring the flag on shipped migrations changes their content_hash (audit-only drift). How should the flag be declared?

## Options

- Edit + accept drift
- Declare runner-side
- Edit + pin hash sources
- Other

## Final answer

Edit + accept drift: declare the ClassVar on each affected migration class, accept the one-time audit-only drift, and record the reason in the PR, changelog and an ADR 2026-10-17-1 note.

## Rationale

_(none)_

## Change log

- `2026-10-20T10:48:25.415474+00:00` — opened
- `2026-10-20T10:48:28.662900+00:00` — resolved (final_answer="Edit + accept drift: declare the ClassVar on each affected migration class, accept the one-time audit-only drift, and record the reason in the PR, changelog and an ADR 2026-10-17-1 note.")
