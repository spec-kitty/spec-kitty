# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-07 · planner-priti · [planning] Accept exactly two same-Mission surfaces: owned.mission_dir through the existing fast path and canonical STATUS_STATE.read_dir through mission_context_for only on inequality. Keep CharterScope.resolve anchored to owned_root/mission_dir and retain every foreign-path refusal.
