# Decision Moment `01M78XBQS8NE8PPMSTZHMDJ610`

- **Mission:** `mission-base-window-bound-01M78XB4`
- **Origin flow:** `specify`
- **Slot key:** `specify.design.base-source`
- **Input key:** `mission_base_source`
- **Status:** `resolved`
- **Created:** `2026-11-12T22:16:56.872223+00:00`
- **Resolved:** `2026-11-12T22:16:59.501939+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does the reconciliation windows' lower bound (the Mission base) come from?

## Options

- Record + derive
- Record only
- merge-base(target, mission)
- Lane bases only

## Final answer

Record + derive: new meta.json mission_base_sha recorded at create/mint; existing Missions derive it (see specify.design.base-derivation); else fall back fail-closed to today's target bound; report recorded vs derived.

## Rationale

_(none)_

## Change log

- `2026-11-12T22:16:56.872223+00:00` - opened
- `2026-11-12T22:16:59.501939+00:00` - resolved (final_answer="Record + derive: new meta.json mission_base_sha recorded at create/mint; existing Missions derive it (see specify.design.base-derivation); else fall back fail-closed to today's target bound; report recorded vs derived.")
