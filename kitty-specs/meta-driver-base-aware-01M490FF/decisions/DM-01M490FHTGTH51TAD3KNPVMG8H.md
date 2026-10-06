# Decision Moment `01M490FHTGTH51TAD3KNPVMG8H`

- **Mission:** `meta-driver-base-aware-01M490FF`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.target-authoritative-precedence`
- **Input key:** `target_authoritative_precedence`
- **Status:** `resolved`
- **Created:** `2026-10-06T16:24:22.096210+00:00`
- **Resolved:** `2026-10-06T17:06:16.698584+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

In the mission-to-target squash context, should target-authoritative meta.json keys (acceptance/VCS provenance, mission_number, status, merged_*) win only on a genuine both-sides conflict (base-aware; a mission-only change to such a key then survives), or always win as today?

## Options

- win only on genuine conflict (base-aware, recommended)
- always win (today rule, base ignored for these keys)
- Other

## Final answer

win only on genuine conflict (base-aware, recommended)

## Rationale

_(none)_

## Change log

- `2026-10-06T16:24:22.096210+00:00` — opened
- `2026-10-06T17:06:16.698584+00:00` — resolved (final_answer="win only on genuine conflict (base-aware, recommended)")
