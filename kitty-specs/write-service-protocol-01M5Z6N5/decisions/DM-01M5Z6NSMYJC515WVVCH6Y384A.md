# Decision Moment `01M5Z6NSMYJC515WVVCH6Y384A`

- **Mission:** `write-service-protocol-01M5Z6N5`
- **Origin flow:** `specify`
- **Slot key:** `specify.auth.bearer-declaration`
- **Input key:** `bearer_declaration`
- **Status:** `resolved`
- **Created:** `2026-10-27T17:31:37.502649+00:00`
- **Resolved:** `2026-10-27T17:31:39.362435+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should the contract declare the bearer token, given layout_check refuses a root components key?

## Options

- Amend layout_check
- x-extension + prose
- Other

## Final answer

Amend layout_check: allow exactly root components.securitySchemes (nothing else under components), with a negative fixture and README rule; the contract uses a standard security requirement.

## Rationale

_(none)_

## Change log

- `2026-10-27T17:31:37.502649+00:00` — opened
- `2026-10-27T17:31:39.362435+00:00` — resolved (final_answer="Amend layout_check: allow exactly root components.securitySchemes (nothing else under components), with a negative fixture and README rule; the contract uses a standard security requirement.")
