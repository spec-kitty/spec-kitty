# Design decisions — lane-worktree-model-hardening-01M6QY1M

The operator rulings (stijn-dejongh, 2026-11-06) are recorded as resolved Decision Moments in this Mission
(`spec-kitty agent decision list --mission lane-worktree-model-hardening-01M6QY1M`).

- **[2026-11-06][specify] Ruling 3 restated (operator, escalation answer).** Lane checkouts never show status files, lanes never change them, readers never read them; the fork-time blob stays in lane history. Removing the files from lane trees would delete the real log at consolidation and break ADR 2026-07-29-1 Assert A'.
- **[2026-11-06][specify] S7 becomes deferred materialization (operator, escalation answer).** Without an explicit `--topology`, `create` mints one Mission topic branch only; lanes, worktrees and the coordination branch are created at finalize once the size rule settles the topology. Rationale (operator): compressing lanes/coord into single_branch is the most expensive transition; growing is cheap.
- **[2026-11-06][specify] S8 back-compat is refuse-plus-attest (operator).** Unstamped single_branch approvals refuse APPROVAL_STAMP_MISSING after upgrade; `--attest-approved-reviewed` lifts per WP. Commit-to-target Missions stay an unbounded residual (recorded in the ADR amendment).
- **[2026-11-06][specify] S5 is a seam now (operator).** One lane-cleanup module behind a remover port; kept lanes are reported, never a traceback after a verified landing; ADR 2026-11-06-1 amendment drafted; binding to destructive_guard after #7275 merges.
- **[2026-11-06][specify] S8 stamp is the Mission write-branch head, gated on the stored single_branch topology (never on `is_planning_lane`), code `LANE_MOVED_AFTER_APPROVAL` reused.** Keeps the orchestrator-api contract unchanged.
