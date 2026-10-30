# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi/deepseek-v4.1-flash-1017 · Issue #6728 removes a typing sentinel, not a behaviour: the deliverable is a named RunScope (FULL | TOPIC_SCOPED) that owns the dead-edge filter derivation, replacing the dead_edge_regenerated_urns '...' default on _is_legacy_applies/legacy_applies_edges. Smallest viable diff: no new module; merge_project_overlay keeps its exported topic_scoped bool and converts to the enum once.

2026-10-30 · pi/deepseek-v4.1-flash-1017 · Analysis recorded before implementation: verdict ready, 1 medium + 2 low; the medium was a real forward-compat defect (a docs-only WP classed as code_change).
