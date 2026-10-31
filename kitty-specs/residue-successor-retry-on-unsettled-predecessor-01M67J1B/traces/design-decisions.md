# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · D1: derive the successor's settlement from the predecessor's recorded outcome (issue route 2), not from an adoption-baseline provenance marker (route 1 edits the frozen backfill) nor a target_version move (route 3 changes manifest semantics). One registry predicate answers for selection and for the runner's skip gate via reselect_when_recorded.

2026-10-30 · claude · D2: detect() stays the idempotency guard. The rule changes who is re-evaluated, never what is re-applied; a second upgrade on a repaired project reports no changes and leaves the tree byte-identical (proved on all four pairs).
