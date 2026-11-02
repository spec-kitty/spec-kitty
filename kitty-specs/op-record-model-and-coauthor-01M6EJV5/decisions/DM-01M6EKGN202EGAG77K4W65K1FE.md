# Decision Moment `01M6EKGN202EGAG77K4W65K1FE`

- **Mission:** `op-record-model-and-coauthor-01M6EJV5`
- **Origin flow:** `plan`
- **Slot key:** `plan.attribution.trailer-source`
- **Input key:** `trailer_source`
- **Status:** `resolved`
- **Created:** `2026-11-02T17:04:36.928263+00:00`
- **Resolved:** `2026-11-02T17:04:42.334124+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does the operator's Co-Authored-By trailer come from?

## Options

- Only a per-close CLI flag
- Only .kittify/config.yaml commit.co_author
- Configured commit.co_author plus a per-close override

## Final answer

Configured commit.co_author in .kittify/config.yaml plus a per-close override (executor argument, exposed as profile-invocation complete --co-author). The standing configuration is what the issue asks for (no per-session hand work); the override covers harnesses whose operator identity is not in the project config, and gives the tests a second path that proves precedence.

## Rationale

_(none)_

## Change log

- `2026-11-02T17:04:36.928263+00:00` — opened
- `2026-11-02T17:04:42.334124+00:00` — resolved (final_answer="Configured commit.co_author in .kittify/config.yaml plus a per-close override (executor argument, exposed as profile-invocation complete --co-author). The standing configuration is what the issue asks for (no per-session hand work); the override covers harnesses whose operator identity is not in the project config, and gives the tests a second path that proves precedence.")
