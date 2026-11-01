# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · pi/deepseek-v4.1-flash-1017 · Grounded on main @ 287a226cfe: gather_artifact_presence already accepts run_dir (added by #6315/#6332) but no production caller supplies it, so _wp_driven_fact always re-resolves from feature_dir.name. Fix is a threading exercise, not new logic.
