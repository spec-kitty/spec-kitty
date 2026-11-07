# Decision Moment `01M6VYWC2HY15NMB81FPB4GD4K`

- **Mission:** `nightly-reds-remediation-01M6VYS1`
- **Origin flow:** `plan`
- **Slot key:** `plan.verification.red_first`
- **Input key:** `red_first_evidence`
- **Status:** `resolved`
- **Created:** `2026-11-07T21:33:22.897472+00:00`
- **Resolved:** `2026-11-07T21:33:24.155174+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is RED-first proof produced and recorded for nightly-only nodes?

## Options

_(none)_

## Final answer

Before editing, each WP runs its exact node ids on the current tree and records the failure; after the edit it re-runs the same ids plus the owning files and named gates. Counts go in the WP's commit message and the final report. Strength-preservation is spot-checked by temporarily reverting one guarded behaviour where cheap (not committed).

## Rationale

_(none)_

## Change log

- `2026-11-07T21:33:22.897472+00:00` - opened
- `2026-11-07T21:33:24.155174+00:00` - resolved (final_answer="Before editing, each WP runs its exact node ids on the current tree and records the failure; after the edit it re-runs the same ids plus the owning files and named gates. Counts go in the WP's commit message and the final report. Strength-preservation is spot-checked by temporarily reverting one guarded behaviour where cheap (not committed).")
