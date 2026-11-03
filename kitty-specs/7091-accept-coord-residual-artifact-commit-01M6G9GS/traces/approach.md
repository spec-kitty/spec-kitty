# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi/deepseek-v4.1-flash-1017 · Reproduced #7091 exactly on main d18c4f1d58 with a throwaway real-worktree fixture: dirtying only the coordination worktree's mission-events.jsonl makes _run_residual_acceptance_commit group it PRIMARY (kind None), and safe_commit refuses the .worktrees/ path. A spike adding a COORD kind made the same call commit both the matrix and the log to the coordination branch with the primary branch untouched.
