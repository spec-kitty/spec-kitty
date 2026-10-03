# Decision Moment `01M41NVK4T6Y912R0JBYS0A5DH`

- **Mission:** `wp-snapshot-backfill-01M41NSY`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.finished-mission-policy`
- **Input key:** `finished_mission_policy`
- **Status:** `resolved`
- **Created:** `2026-10-03T20:04:01.306510+00:00`
- **Resolved:** `2026-10-03T20:04:03.178730+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How to treat finished Missions with missing/partial event logs?

## Options

- exempt_done
- backfill_planned
- backfill_terminal
- Other

## Final answer

backfill_terminal: seed planned plus forced done for finished Missions so progress counts stay true; reducer unchanged (ADR 2026-06-07-3)

## Rationale

_(none)_

## Change log

- `2026-10-03T20:04:01.306510+00:00` — opened
- `2026-10-03T20:04:03.178730+00:00` — resolved (final_answer="backfill_terminal: seed planned plus forced done for finished Missions so progress counts stay true; reducer unchanged (ADR 2026-06-07-3)")
