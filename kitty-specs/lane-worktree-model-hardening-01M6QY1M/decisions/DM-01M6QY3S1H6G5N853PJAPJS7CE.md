# Decision Moment `01M6QY3S1H6G5N853PJAPJS7CE`

- **Mission:** `lane-worktree-model-hardening-01M6QY1M`
- **Origin flow:** `specify`
- **Slot key:** `specify.rulings.status-source-of-truth`
- **Input key:** `status_source_of_truth`
- **Status:** `resolved`
- **Created:** `2026-11-06T08:02:59.249679+00:00`
- **Resolved:** `2026-11-06T08:03:01.621527+00:00`
- **Resolved by:** `stijn-dejongh`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Ruling 8: what is the source of truth for status reads?

## Options

_(none)_

## Final answer

The resolved status surface is the only source of truth; a lane worktree's own status files never count (#6466, #6884).

## Rationale

Operator ruling, stijn-dejongh, 2026-11-06 (epic #7276). Quoted as given.

## Change log

- `2026-11-06T08:02:59.249679+00:00` - opened
- `2026-11-06T08:03:01.621527+00:00` - resolved (final_answer="The resolved status surface is the only source of truth; a lane worktree's own status files never count (#6466, #6884).")
