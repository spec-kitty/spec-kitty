# Decision Moment `01M59YBWHVFWMJJR9ZK24YG7E0`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.authority`
- **Input key:** `ledger_authority`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:22:21.116002+00:00`
- **Resolved:** `2026-10-19T11:22:24.872284+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Where do allow and deny state live? (operator ruling in the mission brief)

## Options

_(none)_

## Final answer

New .kittify/charter/activation.yaml is the single authority for activated_<kind> (three-state) and deactivated_<kind> deny-lists; effective = allow (or all) minus deny; empty deny-lists omitted; other surfaces derive from it and doctor reports divergence.

## Rationale

_(none)_

## Change log

- `2026-10-19T11:22:21.116002+00:00` — opened
- `2026-10-19T11:22:24.872284+00:00` — resolved (final_answer="New .kittify/charter/activation.yaml is the single authority for activated_<kind> (three-state) and deactivated_<kind> deny-lists; effective = allow (or all) minus deny; empty deny-lists omitted; other surfaces derive from it and doctor reports divergence.")
