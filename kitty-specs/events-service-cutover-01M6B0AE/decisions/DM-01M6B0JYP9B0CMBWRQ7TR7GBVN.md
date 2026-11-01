# Decision Moment `01M6B0JYP9B0CMBWRQ7TR7GBVN`

- **Mission:** `events-service-cutover-01M6B0AE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.dev-setup-asset-set`
- **Input key:** `dev_setup_asset_set`
- **Status:** `resolved`
- **Created:** `2026-11-01T07:36:06.089210+00:00`
- **Resolved:** `2026-11-01T07:36:13.206210+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which pinned assets does make dev-setup fetch: everything for this host (incl. the ~95 MB read-service binary) or only the extras (fixtures, bundles, tools)?

## Options

- extras only
- everything for this host
- Other

## Final answer

extras only: make dev-setup runs sync-services with --extras-only (fixtures, bundles, tools); make sync-services keeps fetching everything for this host. Resolved from the operator brief (non-interactive dispatch): it asks to add sync-services to dev-setup and keeps the read service off user machines (decision 2); the binary is needed only by the nightly compare and the release check.

## Rationale

_(none)_

## Change log

- `2026-11-01T07:36:06.089210+00:00` — opened
- `2026-11-01T07:36:13.206210+00:00` — resolved (final_answer="extras only: make dev-setup runs sync-services with --extras-only (fixtures, bundles, tools); make sync-services keeps fetching everything for this host. Resolved from the operator brief (non-interactive dispatch): it asks to add sync-services to dev-setup and keeps the read service off user machines (decision 2); the binary is needed only by the nightly compare and the release check.")
