# Decision Moment `01M48V9K2YY2V1DH37AT8DHP2S`

- **Mission:** `second-clone-origin-reconciliation-01M48V8W`
- **Origin flow:** `specify`
- **Slot key:** `specify.policy.offline`
- **Input key:** `offline_policy`
- **Status:** `resolved`
- **Created:** `2026-10-06T14:53:43.902091+00:00`
- **Resolved:** `2026-10-06T14:53:47.406977+00:00`
- **Opened by:** `cli`
- **Other answer:** `true`

## Question

When a remote is configured but unreachable at a terminus gate, what happens?

## Options

- Fail closed + opt-out
- Warn, use last fetch
- Never fetch at gates
- Other

## Final answer

Fail closed + opt-out, with an env variable to default opt-out of remote/local enforcement

## Rationale

_(none)_

## Change log

- `2026-10-06T14:53:43.902091+00:00` — opened
- `2026-10-06T14:53:47.406977+00:00` — resolved (final_answer="Fail closed + opt-out, with an env variable to default opt-out of remote/local enforcement")
