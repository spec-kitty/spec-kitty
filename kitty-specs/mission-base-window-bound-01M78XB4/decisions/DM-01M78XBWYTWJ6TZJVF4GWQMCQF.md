# Decision Moment `01M78XBWYTWJ6TZJVF4GWQMCQF`

- **Mission:** `mission-base-window-bound-01M78XB4`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.base-derivation`
- **Input key:** `mission_base_derivation`
- **Status:** `resolved`
- **Created:** `2026-11-12T22:17:02.170459+00:00`
- **Resolved:** `2026-11-12T22:17:05.068573+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

For Missions without a recorded mission_base_sha, how is the base derived? (Corrects an earlier lane-base recommendation found unsound by the challenger.)

## Options

- Scaffold parent
- Keep lane base
- Record only

## Final answer

Scaffold parent: first parent of the earliest first-parent commit on the Mission branch that adds kitty-specs/<slug>/; not derivable -> today's target bound (fail-closed).

## Rationale

_(none)_

## Change log

- `2026-11-12T22:17:02.170459+00:00` - opened
- `2026-11-12T22:17:05.068573+00:00` - resolved (final_answer="Scaffold parent: first parent of the earliest first-parent commit on the Mission branch that adds kitty-specs/<slug>/; not derivable -> today's target bound (fail-closed).")
