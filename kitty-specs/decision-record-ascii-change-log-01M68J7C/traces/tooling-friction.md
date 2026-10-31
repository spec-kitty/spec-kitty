# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/deepseek-v4.1-flash-1017 · The root checkout had to carry planning artifacts on a topic branch: 'spec-kitty plan' requires spec.md committed at the primary checkout HEAD, and finalize-tasks refuses to commit planning artifacts to the protected 'main'. Resolved by creating issue-6579-decision-record-ascii from origin/main, moving the three planning commits onto it, and persisting target_branch with finalize-tasks --target-branch. No lane worktree has a .venv, so tests ran through the root clone's venv with PYTHONPATH=<lane>/src:<lane> rather than a per-lane uv sync.
