# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi · Reporting a review rejection via 'spec-kitty next --result failed' sets blocked_reason="Previous step 'implement' failed; manual intervention required" on the mission run and there is no CLI unblock command: every later next call (even --result success) returns kind=blocked. Recovered by clearing blocked_reason (and the un-completed 'implement' entry) in .kittify/runtime/runs/<id>/state.json, which is gitignored local state. An unblock seam, or treating a for_review WP as superseding the failed implement step, would remove the manual step.
