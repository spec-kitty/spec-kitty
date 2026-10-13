# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-13 · Stijn Dejongh · DEVIATION FROM BRIEF (flagged): the brief's 'route the manifest glob via the router FILTER GROUP only; keep registry roots src-only' is infeasible under test_router_src_filters_derive_from_scrub_verbatim, which list-equals a scrub-backed group's router globs to its scrub roots. To select the charter/dossier MODULES the glob must be in the scrub root too. The file-specific glob avoids the mirror-pollution the brief actually warns about (that was the broad packs/built-in/missions/** glob). Precedent: the ci group already carries non-src roots scripts/ci/** + .github/workflows/**.
