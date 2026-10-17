# Decision Moment `01M55KHFFMTF0N8FE1TWG3BEZ5`

- **Mission:** `owned-issue-verdict-authority-01M55KGY`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.coord_owned_read`
- **Input key:** `coord_owned_read_scope`
- **Status:** `resolved`
- **Created:** `2026-10-17T18:56:12.276730+00:00`
- **Resolved:** `2026-10-17T19:09:27.817123+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Scope boundary: mirror #6023 exactly (owned PR-bound single_branch verdict write only), or also thread owned through the coord-owned read path (coord_read_dir_for)?

## Options

- mirror-6023-write-only
- include-coord-owned-read
- Other

## Final answer

include-coord-owned-read: thread owned through both the fail-closed write-target gate (command + resolve_for_write + mission_runtime write_target_degrade) AND the coord-owned read path (coord_read_dir_for / _resolve_read_dir / _migrate_if_needed), so owned verdicts work for owned single_branch (primary case) and owned coord topologies.

## Rationale

_(none)_

## Change log

- `2026-10-17T18:56:12.276730+00:00` — opened
- `2026-10-17T19:09:27.817123+00:00` — resolved (final_answer="include-coord-owned-read: thread owned through both the fail-closed write-target gate (command + resolve_for_write + mission_runtime write_target_degrade) AND the coord-owned read path (coord_read_dir_for / _resolve_read_dir / _migrate_if_needed), so owned verdicts work for owned single_branch (primary case) and owned coord topologies.")
