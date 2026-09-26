# Decision Moment `01M3F3T1G2RYW7P0ZVWQS41GEZ`

- **Mission:** `ratchet-baseline-census-gate-remediation-01M3EW3Z`
- **Origin flow:** `plan`
- **Slot key:** `atdd_exception_deletion_wps`
- **Input key:** `atdd_exception_deletion_wps`
- **Status:** `resolved`
- **Created:** `2026-09-26T15:02:16.322140+00:00`
- **Resolved:** `2026-09-26T15:02:20.009678+00:00`
- **Resolved by:** `operator (stijn@sddevelopment.be via AskUserQuestion)`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Charter ATDD-First (C-011) exception for deletion-only WPs WP07 and WP09, where no honest failing-first test exists?

## Options

- record-exception-wp07-wp09
- keep-import-red-or-drop

## Final answer

record-exception-wp07-wp09

## Rationale

Operator-approved 2026-09-26 (analysis D1 then N1). WP09 deletes duplicated status-parity invariants; WP07 retires a converter whose gate is already gone. Substitutes: WP09 committed mutation matrix (base + lane head); WP07 base evidence (audit.py exit 1, 8 missing/8 ghost rows) plus 8 survivor scanner tests green. WP05 keeps its honest RED.

## Change log

- `2026-09-26T15:02:16.322140+00:00` — opened
- `2026-09-26T15:02:20.009678+00:00` — resolved (final_answer="record-exception-wp07-wp09")
