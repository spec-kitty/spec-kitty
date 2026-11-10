# Decision Moment `01M73HKG7WSR4VDRFXG9JWTGM8`

- **Mission:** `runtime-status-read-door-01M73HHB`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.dm1_owned_coord_read`
- **Input key:** `dm1_owned_coord_read`
- **Status:** `resolved`
- **Created:** `2026-11-10T20:15:16.220052+00:00`
- **Resolved:** `2026-11-10T20:15:18.873918+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

DM-1 owned coordination Mission with an empty or unmaterialized coordination worktree: what do next and query read?

## Options

_(none)_

## Final answer

Query and progress read the committed coordination ref; only an advancing dispatch refuses with OWNED_COORDINATION_WORKSPACE_UNAVAILABLE; ADR 2026-11-06-2 is amended to name this split. (operator interview 2026-11-10, recorded before Mission creation)

## Rationale

_(none)_

## Change log

- `2026-11-10T20:15:16.220052+00:00` - opened
- `2026-11-10T20:15:18.873918+00:00` - resolved (final_answer="Query and progress read the committed coordination ref; only an advancing dispatch refuses with OWNED_COORDINATION_WORKSPACE_UNAVAILABLE; ADR 2026-11-06-2 is amended to name this split. (operator interview 2026-11-10, recorded before Mission creation)")
