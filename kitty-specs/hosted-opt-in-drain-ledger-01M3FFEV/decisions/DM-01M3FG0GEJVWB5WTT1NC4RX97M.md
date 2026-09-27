# Decision Moment `01M3FG0GEJVWB5WTT1NC4RX97M`

- **Mission:** `hosted-opt-in-drain-ledger-01M3FFEV`
- **Origin flow:** `plan`
- **Slot key:** `plan.config.global-home`
- **Input key:** `drain_global_home`
- **Status:** `resolved`
- **Created:** `2026-09-26T18:35:31.154206+00:00`
- **Resolved:** `2026-09-26T18:35:33.772693+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which user-global config.toml holds the personal drain activation?

## Options

_(none)_

## Final answer

Runtime root config.toml (get_runtime_root().base, ~/.spec-kitty on POSIX, SPEC_KITTY_HOME-overridable) as [hosted] drain — co-located with [sync].server_url and hosted credentials.

## Rationale

_(none)_

## Change log

- `2026-09-26T18:35:31.154206+00:00` — opened
- `2026-09-26T18:35:33.772693+00:00` — resolved (final_answer="Runtime root config.toml (get_runtime_root().base, ~/.spec-kitty on POSIX, SPEC_KITTY_HOME-overridable) as [hosted] drain — co-located with [sync].server_url and hosted credentials.")
