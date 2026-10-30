# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · python-pedro · The pre-review gate's 300s review.test_timeout_seconds budget was exceeded on the first WP01 move-task (it also builds a fresh lane venv). Retry passed; the budget was NOT raised, because raising a timeout to pass a gate is gate weakening.
