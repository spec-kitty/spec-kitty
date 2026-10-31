# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · D-1/D-2: fix the read set (explicit domain scope on load_offering_catalog, default = all eight domains) instead of adding a render cache, TTL or --no-charter-render flag; triage records no cache architecture pre-approved and a cache hides the over-read behind invalidation bugs.

2026-10-31 · reviewer-renata · Aggregate review: both WPs approved; integrated diff is 6 source/test modules plus docs. Cross-cutting checks: no specify_cli import added to charter; no new cross-process cache; catalog default behaviour unchanged (C-004); warning contract untouched (C-003); census guards are deterministic and no wall clock is asserted (NFR-004 reported in traces).
