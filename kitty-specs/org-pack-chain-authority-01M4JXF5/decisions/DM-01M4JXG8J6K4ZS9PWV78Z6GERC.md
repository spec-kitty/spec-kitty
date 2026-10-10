# Decision Moment `01M4JXG8J6K4ZS9PWV78Z6GERC`

- **Mission:** `org-pack-chain-authority-01M4JXF5`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.stack-vs-6005`
- **Input key:** `stack_on_6005`
- **Status:** `resolved`
- **Created:** `2026-10-10T12:44:43.974565+00:00`
- **Resolved:** `2026-10-10T12:44:57.079165+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should this mission subsume open PR #6005, stack on top of it, or stay independent and leave the retry loop?

## Options

- Stack on #6005 (lands first; generalize + retire loop on top)
- Subsume #6005
- Independent, leave retry loop

## Final answer

Stack on #6005: it lands first with its full-chain --include/activate fix; this mission generalizes the chain read to every surface via one resolve_pack_chain() authority and retires the _activate_cascade_target retry loop on top.

## Rationale

_(none)_

## Change log

- `2026-10-10T12:44:43.974565+00:00` — opened
- `2026-10-10T12:44:57.079165+00:00` — resolved (final_answer="Stack on #6005: it lands first with its full-chain --include/activate fix; this mission generalizes the chain read to every surface via one resolve_pack_chain() authority and retires the _activate_cascade_target retry loop on top.")
