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
