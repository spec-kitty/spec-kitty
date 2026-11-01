# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi · spec-commit refused planning artifacts because the mission's target_branch was protected main while the checkout sat on a topic branch; the documented remedy was to target the issue branch (mission meta target_branch) rather than the env override, which the Op writer then also requires. Also: make test-fast took 386s against the 300s pre-review gate budget on this shared 20-agent host, so one for_review move hit Pre-review regression gate timed_out and passed unchanged on retry.
