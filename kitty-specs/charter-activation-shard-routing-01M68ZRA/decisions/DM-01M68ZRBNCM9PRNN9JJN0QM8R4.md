# Decision Moment `01M68ZRBNCM9PRNN9JJN0QM8R4`

- **Mission:** `charter-activation-shard-routing`
- **Origin flow:** `specify`
- **Step id:** `specify.success_criteria`
- **Input key:** `success_criteria`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:43:05.772593+00:00`
- **Resolved:** `2026-10-31T12:44:37.150318+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

How will we know this Mission is successful?

## Options

_(none)_

## Final answer

select_modules returns charter for .kittify/charter/charter.yaml, .kittify/charter/activation.yaml and packs/internal.source.yaml; src/kernel/activation_ledger_store.py selects both charter and kernel; an unmapped src/** path alongside an activation-store path still forces run-all; docs-only selects zero modules; all CI-integrity architectural gates stay green with no assertion removed.

## Rationale

_(none)_

## Change log

- `2026-10-31T12:43:05.772593+00:00` — opened
- `2026-10-31T12:44:37.150318+00:00` — resolved (final_answer="select_modules returns charter for .kittify/charter/charter.yaml, .kittify/charter/activation.yaml and packs/internal.source.yaml; src/kernel/activation_ledger_store.py selects both charter and kernel; an unmapped src/** path alongside an activation-store path still forces run-all; docs-only selects zero modules; all CI-integrity architectural gates stay green with no assertion removed.")
