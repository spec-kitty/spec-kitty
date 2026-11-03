# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · Reproduced #7128 in-process on f1e860a17f: in this synced clone _dirty_paths(repo) is empty, collect_material_inputs yields 110 pack-relative paths, and the untracked-material rule in record_report_transaction adds exactly the 67 files under the gitignored, pin-fetched packs/internal tree -> DIRTY_ANALYSIS_INPUT before write. The report-only mode is unusable in the documented make sync-packs setup.

2026-11-03 · python-pedro · WP01 red-first: added the four end-to-end cases first and ran them against unmodified src — the positive case failed with DIRTY_ANALYSIS_INPUT listing packs/internal/{drg/fragment.yaml,org-charter.yaml,pack.yaml,procedures/proof.procedure.yaml}, i.e. the reported refusal, on a fixture that reproduces the sync-packs clone shape. The three controls (one byte changed in the tree, uncommitted pin, unrelated ignored .kittify/templates input) refused both before and after; their non-vacuity comes from the positive case on the same fixture.
