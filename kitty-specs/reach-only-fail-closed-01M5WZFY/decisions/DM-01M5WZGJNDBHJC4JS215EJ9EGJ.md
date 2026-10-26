# Decision Moment `01M5WZGJNDBHJC4JS215EJ9EGJ`

- **Mission:** `reach-only-fail-closed-01M5WZFY`
- **Origin flow:** `specify`
- **Slot key:** `specify.failure.both-unreadable`
- **Input key:** `both_unreadable_behaviour`
- **Status:** `resolved`
- **Created:** `2026-10-26T20:47:57.613904+00:00`
- **Resolved:** `2026-10-26T20:48:09.956407+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When neither the synthesis manifest nor the created-artifacts record can be read, what should reach-only membership do?

## Options

- Treat every synthesis-edge target as reach-only (no roots) and warn
- Raise a named error
- Other

## Final answer

Treat every synthesis-edge target as reach-only (no roots) and warn (operator ruling relayed by the orchestrator, 2026-10-26)

## Rationale

_(none)_

## Change log

- `2026-10-26T20:47:57.613904+00:00` — opened
- `2026-10-26T20:48:09.956407+00:00` — resolved (final_answer="Treat every synthesis-edge target as reach-only (no roots) and warn (operator ruling relayed by the orchestrator, 2026-10-26)")
