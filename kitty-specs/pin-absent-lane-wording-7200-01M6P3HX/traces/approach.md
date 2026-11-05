# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · pi:deepseek-v4.1-flash-1017:python-pedro:implementer · Grounded on current main b4d1e918e2. The issue reproduces exactly: the target test passes when `local_fact` in `wp_evidence.absent_lane_window_cause` is mutated from `does not exist in this checkout` to `is unavailable`, so the absence sentence is unpinned. Scope is the named test plus an internal changelog fragment; no production edit.
