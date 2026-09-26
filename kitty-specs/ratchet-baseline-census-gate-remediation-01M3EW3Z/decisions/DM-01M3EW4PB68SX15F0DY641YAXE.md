# Decision Moment `01M3EW4PB68SX15F0DY641YAXE`

- **Mission:** `ratchet-baseline-census-gate-remediation-01M3EW3Z`
- **Origin flow:** `specify`
- **Slot key:** `scope_3026_inert_slots`
- **Input key:** `scope_3026_inert_slots`
- **Status:** `resolved`
- **Created:** `2026-09-26T12:48:16.742778+00:00`
- **Resolved:** `2026-09-26T12:53:42.781642+00:00`
- **Resolved by:** `operator (stijn@sddevelopment.be via AskUserQuestion)`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#3026: #3285 deleted the cap/anti-weasel/masking tests so the inert-slot caps are dead. Restore those checks and cap the unfireable-owner property (MAX_UNFIREABLE_ENTRIES), or retire the dead machinery and close #3026?

## Options

- restore-and-cap-unfireable
- retire-dead-machinery

## Final answer

retire-dead-machinery

## Rationale

Enforcing tests were removed in #3285; remove the dead caps/predicates/_baselines.yaml keys rather than resurrect them; close #3026 as superseded.

## Change log

- `2026-09-26T12:48:16.742778+00:00` — opened
- `2026-09-26T12:53:42.781642+00:00` — resolved (final_answer="retire-dead-machinery")
