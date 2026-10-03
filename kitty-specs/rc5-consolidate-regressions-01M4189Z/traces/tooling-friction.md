# Tooling friction — rc5-consolidate-regressions

Tooling touched: `spec-kitty` CLI (mission create/specify/plan/tasks/implement/consolidate), git worktrees, uv, codegraph.

- 2026-10-03 — A mission cannot be run from a *linked* git worktree: `locate_project_root`
  (`src/specify_cli/core/paths.py:197`) follows the worktree's `.git` file to the primary
  checkout, so `mission create` would write `kitty-specs/` into the primary checkout (on
  `main`). Worked around by replacing the kick-off's `git worktree add` with a standalone
  clone at the same path/branch/commit (the onboarding cadence's "mission clone"). Candidate
  upstream gap: either document "mission clone, not linked worktree" in the kick-off
  template or detect and refuse with a clear message.
- 2026-10-03 — The Grep tool in this harness is bound to the primary checkout; used `rg` in
  the shell for the mission clone.
