# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · python-pedro · T002/T003: stubbed _supporting_repair_preview with the complete-preview branch and the exact text the golden already pinned (_GOLDEN_DRY_RUN_PREVIEW), plus a call-count assertion. Chose this over seeding the isolated home: seeding would re-create the environment coupling the golden should not have, and every other preview consumer in tests/ already stubs the same seam.
