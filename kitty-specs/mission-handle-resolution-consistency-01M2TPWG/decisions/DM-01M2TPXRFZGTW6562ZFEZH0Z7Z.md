# Decision Moment `01M2TPXRFZGTW6562ZFEZH0Z7Z`

- **Mission:** `mission-handle-resolution-consistency-01M2TPWG`
- **Origin flow:** `specify`
- **Slot key:** `specify.next.single-mission-behavior`
- **Input key:** `next_single_mission_behavior`
- **Status:** `resolved`
- **Created:** `2026-09-18T16:52:18.047459+00:00`
- **Resolved:** `2026-09-18T17:21:27.388409+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When 'spec-kitty next' is run without --mission and exactly one mission exists, should it auto-select that mission and proceed, or list it and require an explicit --mission?

## Options

- Auto-select and proceed
- List and require explicit selection
- Other

## Final answer

Auto-select and proceed: when next is run without --mission and exactly one mission exists, resolve to it and continue (adopt the FR-004 _sole_mission_slug_or_none convention). 0 missions -> structured no-missions error; >1 -> list handles and exit non-usage.

## Rationale

_(none)_

## Change log

- `2026-09-18T16:52:18.047459+00:00` — opened
- `2026-09-18T17:21:27.388409+00:00` — resolved (final_answer="Auto-select and proceed: when next is run without --mission and exactly one mission exists, resolve to it and continue (adopt the FR-004 _sole_mission_slug_or_none convention). 0 missions -> structured no-missions error; >1 -> list handles and exit non-usage.")
