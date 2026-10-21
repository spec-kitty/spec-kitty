# Decision Moment `01M5A6ZKHGQH4PEJ5KWTHM7P2R`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `plan`
- **Slot key:** `plan.migration.dogfood_path`
- **Input key:** `dogfood_migration_path`
- **Status:** `resolved`
- **Created:** `2026-10-19T13:52:55.856636+00:00`
- **Resolved:** `2026-10-19T13:52:59.871253+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

How does this repository get its own activation.yaml (full upgrade touches 4038 files and fails)?

## Options

_(none)_

## Final answer

Add a spec-kitty migrate activation-ledger subcommand (--dry-run) next to the migrate backfill-* commands, running exactly the rc8 migration's planner/apply with the same divergence refusal, and recording it; the mission uses it to migrate this repository's activation keys only.

## Rationale

_(none)_

## Change log

- `2026-10-19T13:52:55.856636+00:00` — opened
- `2026-10-19T13:52:59.871253+00:00` — resolved (final_answer="Add a spec-kitty migrate activation-ledger subcommand (--dry-run) next to the migrate backfill-* commands, running exactly the rc8 migration's planner/apply with the same divergence refusal, and recording it; the mission uses it to migrate this repository's activation keys only.")
