# Decision Moment `01M5ZCANVH16B2ANT1BJ115S8R`

- **Mission:** `charter-cli-typed-errors-json-01M5ZC9Z`
- **Origin flow:** `specify`
- **Slot key:** `specify.json.error-envelope`
- **Input key:** `error_envelope`
- **Status:** `resolved`
- **Created:** `2026-10-27T19:10:24.626018+00:00`
- **Resolved:** `2026-10-27T19:10:27.780452+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which JSON error envelope should charter status/activate/deactivate use?

## Options

- Canonical for new, add code to status
- Canonical everywhere

## Final answer

Canonical everywhere: status, activate and deactivate errors all use {ok:false,error:{code,message}} (json_contract.json_error); status's legacy error envelope is replaced (breaking for status error consumers; CHANGELOG note).

## Rationale

_(none)_

## Change log

- `2026-10-27T19:10:24.626018+00:00` — opened
- `2026-10-27T19:10:27.780452+00:00` — resolved (final_answer="Canonical everywhere: status, activate and deactivate errors all use {ok:false,error:{code,message}} (json_contract.json_error); status's legacy error envelope is replaced (breaking for status error consumers; CHANGELOG note).")
