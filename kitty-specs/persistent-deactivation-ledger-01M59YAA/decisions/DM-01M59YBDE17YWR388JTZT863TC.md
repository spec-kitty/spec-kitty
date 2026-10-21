# Decision Moment `01M59YBDE17YWR388JTZT863TC`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `specify`
- **Slot key:** `specify.compat.older_cli`
- **Input key:** `older_cli_downgrade`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:22:05.633949+00:00`
- **Resolved:** `2026-10-19T11:22:09.480805+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Moving activated_* out of charter.yaml widens activation under an older CLI (absent = all). How to handle?

## Options

_(none)_

## Final answer

Move the keys out (activation.yaml is the only authority); document the downgrade hazard in changelog Upgrade Notes and the ADR; doctor flags activation keys that reappear in charter.yaml/config.yaml.

## Rationale

_(none)_

## Change log

- `2026-10-19T11:22:05.633949+00:00` — opened
- `2026-10-19T11:22:09.480805+00:00` — resolved (final_answer="Move the keys out (activation.yaml is the only authority); document the downgrade hazard in changelog Upgrade Notes and the ADR; doctor flags activation keys that reappear in charter.yaml/config.yaml.")
