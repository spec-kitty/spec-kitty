# Decision Moment `01M56P2ZKF2JAZV1GY7K4ZNM27`

- **Mission:** `charter-preflight-fresh-checkout-01M56P1S`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.committed-drift-data`
- **Input key:** `committed_drift_scope`
- **Status:** `resolved`
- **Created:** `2026-10-18T04:59:57.423041+00:00`
- **Resolved:** `2026-10-18T05:01:35.505644+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should this mission also correct the already-committed drifted manifest on main (re-stamp as a data fix) in addition to the code fix?

## Options

- yes — re-stamp committed manifest too
- no — code fix only; leave data
- other

## Final answer

Yes: also correct the committed drift in this repo's .kittify/charter/synthesis-manifest.yaml (re-stamp bundle_content_hash to match current charter.yaml) as a legitimate data-hygiene fix, distinct from faking the test fixture.

## Rationale

_(none)_

## Change log

- `2026-10-18T04:59:57.423041+00:00` — opened
- `2026-10-18T05:01:35.505644+00:00` — resolved (final_answer="Yes: also correct the committed drift in this repo's .kittify/charter/synthesis-manifest.yaml (re-stamp bundle_content_hash to match current charter.yaml) as a legitimate data-hygiene fix, distinct from faking the test fixture.")
