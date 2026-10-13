# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-13 · Stijn Dejongh · Canonical fix: mint a real `dossier` module and route the file-specific glob packs/built-in/missions/**/expected-artifacts.yaml through the charter + dossier groups in all three verbatim authorities (scrub roots, registry roots, router filter) in lockstep. ATDD gate first (RED on origin/main).

2026-10-13 · Stijn Dejongh · RED-FIRST proof (WP01): pytest tests/architectural/test_manifest_edit_routes_charter_and_dossier.py on origin-main routing content = 5 failed, 1 passed. The 4 manifest params and the self-break precondition fail because select_modules(manifest)==frozenset() on main; the file-specific-glob guard passes (foo.md selects zero code shards).
