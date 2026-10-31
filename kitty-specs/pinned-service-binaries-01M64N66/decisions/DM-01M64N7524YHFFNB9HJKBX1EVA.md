# Decision Moment `01M64N7524YHFFNB9HJKBX1EVA`

- **Mission:** `pinned-service-binaries-01M64N66`
- **Origin flow:** `specify`
- **Slot key:** `specify.launcher.lifecycle-scope`
- **Input key:** `launcher_lifecycle_scope`
- **Status:** `resolved`
- **Created:** `2026-10-29T20:21:58.469006+00:00`
- **Resolved:** `2026-10-29T20:32:26.210407+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How much of the launcher lifecycle does this mission build, given that the write-service binary (command-cli) does not exist yet?

## Options

- Resolve, verify and refuse only; start, health and stale recovery follow with #6195
- Full lifecycle now: start, reuse, health, stale recovery, tested against a fake service that speaks the 2026-10-27-1 protocol
- Other

## Final answer

Full lifecycle now: resolve, verify, start/reuse, health, stale recovery, fail-closed codes; tested against a fake service speaking the ADR 2026-10-27-1 protocol

## Rationale

_(none)_

## Change log

- `2026-10-29T20:21:58.469006+00:00` — opened
- `2026-10-29T20:32:26.210407+00:00` — resolved (final_answer="Full lifecycle now: resolve, verify, start/reuse, health, stale recovery, fail-closed codes; tested against a fake service speaking the ADR 2026-10-27-1 protocol")
