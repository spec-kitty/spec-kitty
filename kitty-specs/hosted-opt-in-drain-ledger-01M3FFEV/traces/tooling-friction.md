# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

## 2026-09-26 — specify
- `agent decision open/resolve` on the fresh coord mission wrote `decisions/` into PRIMARY then raised `CoordinationWorktreeUnmaterialized`; the advertised remedy `doctor workspaces --fix` printed "No workspace husks found." and materialized nothing. Exactly #5113. Removed the partial decision files and recorded the four operator decisions in spec.md until the coord worktree materializes.
- `.claude/`/`.agents/` agent copies are not generated in this checkout, so the `/spec-kitty.*` prompts were followed from `packs/built-in/missions/mission-steps/software-dev/*/prompt.md`.
- Workaround that worked: `spec-commit` of spec.md materialized the coord worktree; after that `decision open/resolve` succeeded. The decision files still land in the PRIMARY working tree (untracked) and `spec-commit` routes them to the coord branch — the split ledger of #5113/#5023 reproduced; primary copies left as the tool's working set.
- Trace files are COORD-partition: `spec-commit` silently routed them to the coord branch while leaving untracked primary copies.
- `implement` refused until `/spec-kitty.analyze` ran (analysis_report_required) — fine, but the bulk-edit inference fired on "rename" in a deferred-follow-up sentence; needed `--acknowledge-not-bulk-edit`.
- Workspace allocation failed: the recorded planning commit carried a primary copy of `status.json` (I had safe-committed the finalize-written primary `status.json`); lanes branch from the coord branch, which adds its own `status.json` → add/add conflict (no merge driver for status.json, unlike status.events.jsonl). Resolved by manual merge keeping the coord-derived copy (needed `git add --sparse`: lanes use sparse checkout). Lesson: never commit primary `status.json` on a coord-topology mission.
- Every new lane hits the same `status.json` add/add conflict twice: once merging the recorded planning commit, once merging each dependency lane (status.json is derived and has no merge driver, unlike status.events.jsonl). Manual resolution each time (keep ours, `git add --sparse`). Candidate upstream gap: register a derived-file merge strategy for `kitty-specs/**/status.json`.
- Gates found late: `move-task --to approved` refuses on ANY issue-matrix row without a terminal verdict — including issues cited only as cross-links in plan/WP prompts (#3030, #4053, #4322, #4737). The gate reported them one batch at a time (unknown rows first, then missing rows).
- Process: implementer subagents used `git stash` in lane worktrees (lane-f 21:56, lane-g 23:09/23:13) despite the explicit ban — the stash stack is shared across worktrees, a real hazard with 3 lanes running in parallel. Caught by the WP07 reviewer via dangling stash commits. Implementer prompts now repeat the ban; consider a pre-commit/hook guard.
