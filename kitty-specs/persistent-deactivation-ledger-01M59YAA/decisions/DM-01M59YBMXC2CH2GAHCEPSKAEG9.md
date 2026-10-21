# Decision Moment `01M59YBMXC2CH2GAHCEPSKAEG9`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `specify`
- **Slot key:** `specify.compat.unmigrated`
- **Input key:** `unmigrated_projects`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:22:13.292683+00:00`
- **Resolved:** `2026-10-19T11:22:16.863826+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

How does the new CLI behave on a project with legacy activated_* and no activation.yaml (pre-upgrade)?

## Options

_(none)_

## Final answer

A migration run is added, so the upgrade takes care of it: the ledger is read only from activation.yaml, no runtime legacy fallback; test fixtures are re-seeded into activation.yaml.

## Rationale

_(none)_

## Change log

- `2026-10-19T11:22:13.292683+00:00` — opened
- `2026-10-19T11:22:16.863826+00:00` — resolved (final_answer="A migration run is added, so the upgrade takes care of it: the ledger is read only from activation.yaml, no runtime legacy fallback; test fixtures are re-seeded into activation.yaml.")
