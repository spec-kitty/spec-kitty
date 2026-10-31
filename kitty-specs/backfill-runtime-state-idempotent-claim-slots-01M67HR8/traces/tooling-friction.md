# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · A freshly created lane worktree has no packs/ tree, so the first test collection died with BuiltInPackMissing after ~95s. The brief warns 'run make sync-packs once in every checkout, lane or coordination worktree'; the failure surfaces only at collection time, with no hint in the worktree that packs are the cause.

2026-10-31 · claude · Post-fix pytest wall time for the same 11 tests alternated between ~2s and ~110s on this shared 20-agent host, with no test-level duration to attribute it to (durations showed <2s). Reads as I/O contention, not the diff.

2026-10-31 · claude · move-task --to approved refuses twice: first the issue matrix must be terminal, then the reviewer identity must differ from the implementer (REVIEW_NOT_INDEPENDENT), and the review verdict is written but not committed (--no-auto-commit), leaving the operator to commit it.
