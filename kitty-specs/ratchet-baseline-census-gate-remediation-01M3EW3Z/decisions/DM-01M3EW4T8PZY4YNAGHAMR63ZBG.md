# Decision Moment `01M3EW4T8PZY4YNAGHAMR63ZBG`

- **Mission:** `ratchet-baseline-census-gate-remediation-01M3EW3Z`
- **Origin flow:** `specify`
- **Slot key:** `scope_5085_census_keys`
- **Input key:** `scope_5085_census_keys`
- **Status:** `resolved`
- **Created:** `2026-09-26T12:48:20.758927+00:00`
- **Resolved:** `2026-09-26T12:53:46.300837+00:00`
- **Resolved by:** `operator (stijn@sddevelopment.be via AskUserQuestion)`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#5085: widen the positional-anchor ban and migrate _KNOWN_JOIN_ALLOWLIST + #3206 kernel exemptions. Are the 80 rel:lineno:op census keys (destructive/mutation/overwrite gates) in scope for this mission or deferred to a follow-up?

## Options

- in-scope
- defer-follow-up-with-enumerated-exemption

## Final answer

in-scope

## Rationale

Operator chose full migration: widen ban, migrate joins + #3206 exemptions, and re-key all 80 rel:lineno:op census keys.

## Change log

- `2026-09-26T12:48:20.758927+00:00` — opened
- `2026-09-26T12:53:46.300837+00:00` — resolved (final_answer="in-scope")
