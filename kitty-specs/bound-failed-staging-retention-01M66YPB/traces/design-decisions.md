# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · The bound is a count (3) ordered by mtime with a name tiebreak, not same-cause replacement: same-cause needs to read every old cause.yaml and destroys the comparison history, while a count bound is deterministic and testable.

2026-10-30 · python-pedro · Deletion goes through PathGuard.rmtree so the synthesizer's single write-seam invariant (ADR 2026-04-17-2) and tests/charter/synthesizer/test_path_guard.py stay true; no allowlist change.
