# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Decided the cause from evidence, not from the issue's proposed diagnosis: the reported short joins are followed by assert is_alive() (load can only make those pass), while the real load-sensitive wall clock is the product's 10 s decisions-lock acquire bound surfacing as a retryable LOCK_TIMEOUT refusal. Fixed the harness by pinning the bound inside the scenario and giving the file one backstop budget.
