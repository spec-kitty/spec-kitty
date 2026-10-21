# Decision Moment `01M59Z0PSD7AP0CX4SCAK8XJPQ`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.deny_writers`
- **Input key:** `deny_writers`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:33:43.341756+00:00`
- **Resolved:** `2026-10-19T11:33:47.005199+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Which write paths may change a deny-list?

## Options

_(none)_

## Final answer

Presets with --force too: only charter activate <kind> <id> (incl. --only), a cascade with --include-deactivated, and charter activate --preset X --force (for ids the preset lists, reported) clear deny entries. Presets without --force, the interview and every other writer never touch deny keys; a denied id they list stays subtracted with a warning. Ids dropped by --only narrowing get no deny entry.

## Rationale

_(none)_

## Change log

- `2026-10-19T11:33:43.341756+00:00` — opened
- `2026-10-19T11:33:47.005199+00:00` — resolved (final_answer="Presets with --force too: only charter activate <kind> <id> (incl. --only), a cascade with --include-deactivated, and charter activate --preset X --force (for ids the preset lists, reported) clear deny entries. Presets without --force, the interview and every other writer never touch deny keys; a denied id they list stays subtracted with a warning. Ids dropped by --only narrowing get no deny entry.")
