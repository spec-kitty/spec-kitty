# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi · Seed: reproduced #6750 on main 512567eee7 with the issue's own recipe (untracked dir + empty hooks dir): HEAD advanced, children landed, collector printed 'could not auto-commit' plus a hook attribution with an empty hook dir. Fix plan: collector expands untracked entries (untracked='all'), preflight refuses a directory pathspec before any mutation, collector reports a landed commit truthfully.
