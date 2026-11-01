# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Ratchet shape: git grep (one process, honours .gitignore, includes --untracked so an uncommitted coupling is caught) prefilters ~29 files that spell a retired name; an AST pass classifies each hit into attribute / from-import / setattr-string forms, so lookalike private helpers in other modules (pack_manager._config_stem, pack_assembler._read_id, lint._default_scan_roots) are not flagged. Planted-source controls per form plus an 'unrelated private helpers' control keep it non-vacuous.

2026-11-01 · python-pedro · read_artifact_id (pass-memoised) and parse_artifact_id (uncached full parse) stay two names on purpose: the scan-count and memoization tests assert the memoised reader is the only seeder of ResolutionPass.ids and compare against the uncached parse. Collapsing them would weaken that assertion.
