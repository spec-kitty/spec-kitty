# Decision Moment `01M3M2ZXH4CGY20X1PZEC18F54`

- **Mission:** `owned-checkout-lifecycle-authority-01M3M2ZB`
- **Origin flow:** `specify`
- **Slot key:** `specify.resolution.stale-primary-copy`
- **Input key:** `stale_primary_copy_policy`
- **Status:** `resolved`
- **Created:** `2026-09-28T13:24:12.452326+00:00`
- **Resolved:** `2026-09-28T13:26:29.225217+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a validated owned checkout holds the mission AND the primary checkout also holds a (stale) copy of the same mission, what should owned-checkout lifecycle reads do?

## Options

- Owned checkout wins silently (primary copy ignored)
- Owned checkout wins, emit a warning naming the stale primary copy
- Refuse with a typed conflict error until the operator removes one copy
- Other

## Final answer

Owned checkout wins, emit a warning naming the stale primary copy

## Rationale

_(none)_

## Change log

- `2026-09-28T13:24:12.452326+00:00` — opened
- `2026-09-28T13:26:29.225217+00:00` — resolved (final_answer="Owned checkout wins, emit a warning naming the stale primary copy")
