# Tooling Friction Log

> Log every place the tooling fought you so it can feed the tooling-gap backlog.

**Prompting questions**
- What tooling or command did you have to work around?
- What blocked you unexpectedly, and how long did it take to unblock?
- Was this a known issue or something discovered fresh?

---

## Entries

<!-- YYYY-MM-DD — 1-3 sentences: what happened, why it slowed you down. -->

- 2026-09-26 — Fresh container had no `.venv` and no generated agent commands; `uv sync --frozen --all-extras` + `spec-kitty doctor skills --fix` restored them, but the fix rewrote the tracked `.kittify/command-skills-manifest.json` (version/hash churn) which had to be reverted by hand.
- 2026-09-26 — `decision open`/`resolve` on the freshly created coord mission wrote the PRIMARY ledger then raised `CoordinationWorktreeUnmaterialized`; the advertised remedy `doctor workspaces --fix` is a no-op. `spec-commit` of the decision files materialized the coord worktree as a side effect and routed them to the coord branch, splitting the ledger. Filed and folded as #5113.
- 2026-09-26 — The onboarding-run doc references `docs/development/pr-landing.md` / `known-friction-points.md` at paths that moved under `how-to/` and `reference/`.
- 2026-09-26 — `spec-commit` routes `traces/*.md` (and `decisions/`) to the local coordination branch, not the planning branch; committed a planning-branch copy by hand so the PR-bound branch carries them (same dual-partition family as #5023/#5113).
- 2026-09-26 — `agent context resolve --action tasks` returns `feature_dir` inside the coordination worktree while `check-prerequisites --include-tasks` returns the primary planning dir; used check-prerequisites (planning artifacts are primary-partition).
- 2026-09-26 — Every lane allocation failed "cannot auto-merge the recorded planning commit": planning-branch mirrors of `traces/` + `status.*` (committed by hand to keep the PR branch durable) diverged from the coord-branch copies `spec-commit` routed there. Resolved per the tool's documented remedy in each lane (merge, keep lane-side `status.json`, commit, re-run implement). Lesson: never mirror coord-partition files onto the planning branch by hand.
- 2026-09-26 — `spec-kitty merge-driver-event-log` "not found" in git subprocesses when the venv is not on PATH; lane worktrees are sparse and exclude `status.json`, so resolving needs `git update-index --cacheinfo` rather than `git add`.
