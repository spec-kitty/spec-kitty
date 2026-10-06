# Decision Moment `01M48H6SZMJV0ZQKQRHDBAB839`

- **Mission:** `retire-runtime-bridge-delegates-01M48H5E`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.facade-reexports`
- **Input key:** `facade_reexports`
- **Status:** `resolved`
- **Created:** `2026-10-06T11:57:26.900409+00:00`
- **Resolved:** `2026-10-06T11:57:29.891396+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Do get_or_start_run and build_operational_context_for_claim stay on runtime_bridge, or are their CLI callers repointed at runtime_bridge_io?

## Options

- Keep as public plain re-exports (same function objects)
- Repoint CLI callers and delete
- Other

## Final answer

Keep as public plain re-exports (same function objects). Operator brief: repointing callers outside src/runtime/next is out of scope; test_no_dead_symbols pins the facade names.

## Rationale

_(none)_

## Change log

- `2026-10-06T11:57:26.900409+00:00` — opened
- `2026-10-06T11:57:29.891396+00:00` — resolved (final_answer="Keep as public plain re-exports (same function objects). Operator brief: repointing callers outside src/runtime/next is out of scope; test_no_dead_symbols pins the facade names.")
