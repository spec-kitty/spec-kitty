# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · The for_review pre-review baseline gate runs the repo's configured review.test_command (make test-fast, 300 s budget) in a detached worktree. On this shared host (load average 100+ from 19 sibling agents) it times out at 300 s every time, so the baseline artifact records 'baseline command timed out' instead of a real baseline; retrying until the host calms is the only non-skipping remedy. Same command took 15 s - 269 s per file run depending on host load.
