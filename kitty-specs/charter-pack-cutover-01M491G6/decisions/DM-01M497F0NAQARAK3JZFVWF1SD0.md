# Decision Moment `01M497F0NAQARAK3JZFVWF1SD0`

- **Mission:** `charter-pack-cutover-01M491G6`
- **Origin flow:** `plan`
- **Slot key:** `plan.migration.minimal-kind-gate`
- **Input key:** `minimal_kind_gate`
- **Status:** `resolved`
- **Created:** `2026-10-06T18:26:24.554861+00:00`
- **Resolved:** `2026-10-06T18:31:32.085064+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Projects that applied the released minimal preset carry activated_kinds: [directives, tactics], which disables six kinds the preset meant to leave open. Should the migration remove that activated_kinds key?

## Options

- Remove it when it equals the released minimal value and report it
- Keep it and report it
- Other

## Final answer

A: remove activated_kinds when it equals the released minimal value [directives, tactics] and report it (owner, 2026-10-06)

## Rationale

_(none)_

## Change log

- `2026-10-06T18:26:24.554861+00:00` — opened
- `2026-10-06T18:31:32.085064+00:00` — resolved (final_answer="A: remove activated_kinds when it equals the released minimal value [directives, tactics] and report it (owner, 2026-10-06)")
