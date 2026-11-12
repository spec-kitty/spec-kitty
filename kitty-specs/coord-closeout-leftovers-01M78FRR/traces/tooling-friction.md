# Tooling friction

Append-only. One entry per friction: date, phase, what happened, workaround, follow-up.

- **[2026-11-12][research] The clone is shallow (50 commits)**, so the 90-day churn the grounding brief asks for cannot be measured. Workaround: noted as unmeasured. Follow-up: none (environment).
- **[2026-11-12][specify] `agent mission create` without `--topology` switched the root checkout to the minted Mission branch** while the target stays `fix/7598-coord-closeout-leftovers`; expected per ADR `2026-11-06-3`, noted because the operator brief assumed work on the fix branch.
- **[2026-11-12][specify] With `auto_commit: false`, `agent decision open/resolve` leave `decisions/` and `status.events.jsonl` uncommitted.** Workaround: commit them by hand (#5763 / #7545 class).
