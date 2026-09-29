# Decision Moment `01M3NSKEGC7QNXA1G3711AP77X`

- **Mission:** `requirement-id-grammar-01M3NRCA`
- **Origin flow:** `specify`
- **Slot key:** `specify.contract.plan-error-code`
- **Input key:** `plan_error_code`
- **Status:** `resolved`
- **Created:** `2026-09-29T05:18:35.532189+00:00`
- **Resolved:** `2026-09-29T05:18:37.014387+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is the setup-plan malformed-ID refusal carried through the orchestrator-api contract?

## Options

- Reason in data
- Register a new contract code
- Other

## Final answer

Reason in data: envelope keeps PLAN_SETUP_FAILED; payload carries typed reason SPEC_REQUIREMENT_IDS_INVALID; direct setup-plan JSON uses that code

## Rationale

_(none)_

## Change log

- `2026-09-29T05:18:35.532189+00:00` — opened
- `2026-09-29T05:18:37.014387+00:00` — resolved (final_answer="Reason in data: envelope keeps PLAN_SETUP_FAILED; payload carries typed reason SPEC_REQUIREMENT_IDS_INVALID; direct setup-plan JSON uses that code")
