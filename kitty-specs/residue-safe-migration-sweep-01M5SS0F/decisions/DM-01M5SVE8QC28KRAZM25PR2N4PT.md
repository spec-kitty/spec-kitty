# Decision Moment `01M5SVE8QC28KRAZM25PR2N4PT`

- **Mission:** `residue-safe-migration-sweep-01M5SS0F`
- **Origin flow:** `plan`
- **Slot key:** `plan.reporting.residue-notice-dedupe`
- **Input key:** `residue_notice_dedupe`
- **Status:** `resolved`
- **Created:** `2026-10-25T15:39:04.300157+00:00`
- **Resolved:** `2026-10-25T15:48:20.037223+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Up to five residue-aware steps (four successors plus the 3.2.0a4 normalization) can skip the same folder in one upgrade run. How is 'reported at most once per folder per run' enforced?

## Options

- Each step warns with the shared text; the upgrade runner collapses identical residue notices across steps
- Steps stay silent during upgrade; the runner prints one residue block after the migrations
- Other

## Final answer

Each step emits the same shared residue text (one constant from the Mission resolver); the upgrade runner collapses repeated identical residue notices for the same folder across steps

## Rationale

_(none)_

## Change log

- `2026-10-25T15:39:04.300157+00:00` — opened
- `2026-10-25T15:48:20.037223+00:00` — resolved (final_answer="Each step emits the same shared residue text (one constant from the Mission resolver); the upgrade runner collapses repeated identical residue notices for the same folder across steps")
