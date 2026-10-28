# Decision Moment `01M5Z6NNXENZAK9XP21FYHZPT5`

- **Mission:** `write-service-protocol-01M5Z6N5`
- **Origin flow:** `specify`
- **Slot key:** `specify.errors.guard-codes`
- **Input key:** `guard_refusal_codes`
- **Status:** `resolved`
- **Created:** `2026-10-27T17:31:33.678681+00:00`
- **Resolved:** `2026-10-27T17:31:35.617062+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Guard/state-machine refusals carry no machine code today. What should the contract's refusal codes be?

## Options

- Reuse codes + mint reasons
- Mint fine-grained codes
- Edge codes only
- Other

## Final answer

Reuse codes + mint reasons: code reuses every existing Python code verbatim (edge codes for guards); the contract mints a closed, provisional reason vocabulary per guard carried in Problem.type as a URN; Python adopting the reasons is a follow-up.

## Rationale

_(none)_

## Change log

- `2026-10-27T17:31:33.678681+00:00` — opened
- `2026-10-27T17:31:35.617062+00:00` — resolved (final_answer="Reuse codes + mint reasons: code reuses every existing Python code verbatim (edge codes for guards); the contract mints a closed, provisional reason vocabulary per guard carried in Problem.type as a URN; Python adopting the reasons is a follow-up.")
