# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · Host contention (load average ~200, 20 concurrent agents) makes heavy gates time out rather than fail: test_no_dead_symbols/test_status_module_boundary pass individually but exceed their pytest-timeout/15s budgets when run together, and the for_review pre-review regression gate first hit its 300s budget. Reported in the PR's Deferred section; no gate was weakened.
