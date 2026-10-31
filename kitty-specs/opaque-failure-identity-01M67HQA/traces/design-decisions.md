# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · opaque-failure-identity-01M67HQA · Bind the opaque identity to (exit status, summary) and compare opaque failures on that bound identity instead of the '<declared-command>' placeholder name. A differing opaque candidate failure is a NEW failure (fail-closed); an identical one stays pre-existing. Rejected the alternative of collapsing every opaque mismatch to unverified_baseline because that still warn-passes a genuine regression.
