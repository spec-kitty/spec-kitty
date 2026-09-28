# Decision Moment `01M3KBSA146T2KZJZ0S0T7CHCZ`

- **Mission:** `squad-doctrine-single-owner-01M3KBP7`
- **Origin flow:** `specify`
- **Slot key:** `specify.consumers.retired_styleguide`
- **Input key:** `consumer_safe_path`
- **Status:** `resolved`
- **Created:** `2026-09-28T06:38:38.628772+00:00`
- **Resolved:** `2026-09-28T06:38:41.480057+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How do projects that activated adversarial-squad-cadence survive its deletion?

## Options

_(none)_

## Final answer

Upgrade migration that strips the retired styleguide id from config.yaml, charter.yaml (activation + catalog) and references.yaml, following the m_3_2_6_retire_rtk_search_tooling precedent (the charter compiler fails closed on an unknown activated id). This repository's own charter surfaces are updated in the same change.

## Rationale

_(none)_

## Change log

- `2026-09-28T06:38:38.628772+00:00` — opened
- `2026-09-28T06:38:41.480057+00:00` — resolved (final_answer="Upgrade migration that strips the retired styleguide id from config.yaml, charter.yaml (activation + catalog) and references.yaml, following the m_3_2_6_retire_rtk_search_tooling precedent (the charter compiler fails closed on an unknown activated id). This repository's own charter surfaces are updated in the same change.")
