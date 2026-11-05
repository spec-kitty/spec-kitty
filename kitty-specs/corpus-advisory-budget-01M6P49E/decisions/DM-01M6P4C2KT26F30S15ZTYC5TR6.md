# Decision Moment `01M6P4C2KT26F30S15ZTYC5TR6`

- **Mission:** `corpus-advisory-budget-01M6P49E`
- **Origin flow:** `plan`
- **Step id:** `plan.risks`
- **Input key:** `risks`
- **Status:** `resolved`
- **Created:** `2026-11-05T15:13:53.786655+00:00`
- **Resolved:** `2026-11-05T15:16:32.209396+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

What are the main risks or unknowns?

## Options

_(none)_

## Final answer

Known risks: the cap guard's block parser is indentation- and neighbour-sensitive (headroom line must sit directly above the job-level timeout-minutes); a step budget at or above the job cap is dead config; the recorded max can drift from reality (the 75% rule forces a cap bump when it grows); editing the suite step could accidentally change the selection (the recorded diff is the check). See plan.md IC-01..IC-03 Risks and WP01 Risks & Mitigations.

## Rationale

_(none)_

## Change log

- `2026-11-05T15:13:53.786655+00:00` — opened
- `2026-11-05T15:16:32.209396+00:00` — resolved (final_answer="Known risks: the cap guard's block parser is indentation- and neighbour-sensitive (headroom line must sit directly above the job-level timeout-minutes); a step budget at or above the job cap is dead config; the recorded max can drift from reality (the 75% rule forces a cap bump when it grows); editing the suite step could accidentally change the selection (the recorded diff is the check). See plan.md IC-01..IC-03 Risks and WP01 Risks & Mitigations.")
