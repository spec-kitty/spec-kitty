# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/claude-sonnet-4.5 · The lane worktree is created without .venv or the fetched packs tree, and 'make sync-packs' inside it re-points the shared .venv's editable install at the lane worktree path. Worked around by symlinking ../../.venv and running make sync-packs in the lane; the primary clone must be re-synced before its tests mean anything. Also: 'spec-kitty tasks' refuses to commit planning artifacts while target_branch is the protected main, so the topic branch has to exist before finalize-tasks, not after.
