# Decision Moment `01M3VJMAFK4G9W5CA9YNQZ05H8`

- **Mission:** `coord-status-log-home-01M3VJKP`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.status-home`
- **Input key:** `status_log_home`
- **Status:** `resolved`
- **Created:** `2026-10-01T11:12:10.739413+00:00`
- **Resolved:** `2026-10-01T11:12:13.472852+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should a coordination mission's status log stay off the target branch: seed it on the coordination branch at create, or let consolidate reconcile a target-side copy?

## Options

- Seed on the coordination branch at create
- Reconcile the target-side copy at consolidate
- Other

## Final answer

Seed on the coordination branch at create

## Rationale

Self-driven per the operator's instruction (thread request 2026-10-01: 'Self-drive as much as you can, based on the charter'). Seeding fixes the defect at its source (issue #5440's primary expected outcome), matches the existing coord fixture shape (STATUS-only husk), and also removes the first-coord-write carry-over gap. Reconciling at consolidate would leave the CLI writing a COORD-partition kind onto the target and only paper over it later.

## Change log

- `2026-10-01T11:12:10.739413+00:00` — opened
- `2026-10-01T11:12:13.472852+00:00` — resolved (final_answer="Seed on the coordination branch at create")
