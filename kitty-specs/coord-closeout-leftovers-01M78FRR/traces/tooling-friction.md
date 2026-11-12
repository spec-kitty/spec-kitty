# Tooling friction

Append-only. One entry per friction: date, phase, what happened, workaround, follow-up.

- **[2026-11-12][research] The clone is shallow (50 commits)**, so the 90-day churn the grounding brief asks for cannot be measured. Workaround: noted as unmeasured. Follow-up: none (environment).
- **[2026-11-12][specify] `agent mission create` without `--topology` switched the root checkout to the minted Mission branch** while the target stays `fix/7598-coord-closeout-leftovers`; expected per ADR `2026-11-06-3`, noted because the operator brief assumed work on the fix branch.
- **[2026-11-12][specify] With `auto_commit: false`, `agent decision open/resolve` leave `decisions/` and `status.events.jsonl` uncommitted.** Workaround: commit them by hand (#5763 / #7545 class).
- **[2026-11-12][implement WP04] `lanes/lane_tip.py::is_absorbed` cannot prove a squash-landed coordination branch absorbed** (plan risk R1 confirmed): `status.events.jsonl` differs by event order and target-only events, `status.json` is an add/add conflict, so `merge-tree --write-tree` conflicts. Workaround: none; WP04 stopped at the red test and escalated with two proof options (see `approach.md`). Follow-up: operator ruling on the proof.
- **[2026-11-12][implement WP04] The terminus harness has no cheap "archived coordination Mission" builder**: each CLI cell runs a real `consolidate` (tens of seconds), so a 9-cell CLI file costs minutes. Workaround: accepted. Follow-up: a cached, copyable fixture would need worktree path rewriting.
