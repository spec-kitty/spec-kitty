# Decision Moment `01M3PD3VP1YTQ4D17HT96JA0T2`

- **Mission:** `consolidation-claim-rollback-integrity-01M3PD1T`
- **Origin flow:** `specify`
- **Slot key:** `specify.rollback.coord-restore`
- **Input key:** `coord_restore_mechanism`
- **Status:** `resolved`
- **Created:** `2026-09-29T10:59:36.257768+00:00`
- **Resolved:** `2026-09-29T10:59:39.254614+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does a failed gate restore the mission/coordination branch?

## Options

- CAS ref restore
- Revert + durable anchor
- Other

## Final answer

CAS ref restore: one persisted pre-mutation snapshot + one CAS rollback authority restoring every captured ref; supersedes AC-B3 revert-only on this path; amend ADR 2026-09-19-1

## Rationale

_(none)_

## Change log

- `2026-09-29T10:59:36.257768+00:00` — opened
- `2026-09-29T10:59:39.254614+00:00` — resolved (final_answer="CAS ref restore: one persisted pre-mutation snapshot + one CAS rollback authority restoring every captured ref; supersedes AC-B3 revert-only on this path; amend ADR 2026-09-19-1")
