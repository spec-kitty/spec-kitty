# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Reproduced #6466 on current main with a real lane worktree: the coord topology keeps status solely on the coordination husk (lane worktrees carry no status copy at all), while the branch-flat lanes topology keeps it on the primary/mission-branch copy — yet a read anchored at the lane worktree root still answered from its fork-time copy.
