# Decision Moment `01M5ZC1PYHBB6QB02YQ4H1V52P`

- **Mission:** `write-service-protocol-01M5Z6N5`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.dead-gate-size`
- **Input key:** `dead_gate_size`
- **Status:** `resolved`
- **Created:** `2026-10-27T19:05:30.833327+00:00`
- **Resolved:** `2026-10-27T19:05:32.790648+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The dead-symbol gate counts every public name, so the typed client shapes need 11 symbol entries plus 1 dead-module entry (net +10 on the 229 cap). How to proceed?

## Options

- New priced category
- Shapes as test reference
- Private helpers
- Other

## Final answer

New priced category: declare the 10 adapter-facing names in __all__, list them and bind_event_bridge under category_c_write_service_client_6675 (requires_issue, #6195), cap 229 -> 239, dead-module category 7 1 -> 2 with TODO(triage) #6195. Supersedes the earlier dead_gate_handling estimate of about two entries.

## Rationale

_(none)_

## Change log

- `2026-10-27T19:05:30.833327+00:00` — opened
- `2026-10-27T19:05:32.790648+00:00` — resolved (final_answer="New priced category: declare the 10 adapter-facing names in __all__, list them and bind_event_bridge under category_c_write_service_client_6675 (requires_issue, #6195), cap 229 -> 239, dead-module category 7 1 -> 2 with TODO(triage) #6195. Supersedes the earlier dead_gate_handling estimate of about two entries.")
