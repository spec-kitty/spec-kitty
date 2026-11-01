# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · Retention is enforced inside StagingDir.commit_to_failed after the current run is preserved, so every refusing caller (synthesize, resynthesize, orchestrator, dry-run) inherits it without a new command or config key.
