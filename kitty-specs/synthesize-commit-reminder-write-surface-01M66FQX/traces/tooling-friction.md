# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-j · First specify run created the mission with target_branch=main (protected); spec-commit refused. Unwound the 6-minute-old mission (coord worktree + branch + untracked scaffold; reverted the 3 aborted lifecycle.jsonl lines) and re-created on the topic branch issue-6631-synthesize-reminder-write-surface. Lesson: create the mission from the topic branch, or pass --start-branch.
