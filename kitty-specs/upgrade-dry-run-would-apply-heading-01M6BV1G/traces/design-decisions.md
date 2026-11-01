# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · Heading and marker are chosen once from result.dry_run in _display_upgrade_results: dry run gets 'Migrations that would be applied:' plus a yellow '→' marker, the real run keeps 'Migrations applied:' plus '✓'. One decision site, so the pair cannot drift; the heading is selected, never force-printed, so an empty list still renders nothing.

2026-11-01 · python-pedro · The dry-run characterization golden (_GOLDEN_APPLIED_DRY_RUN) and the sequenced-verdict CLI assertion are updated on purpose, with #6234 cited in their docstrings; _GOLDEN_APPLIED (real run) is not edited and acts as the positive control that the fix is mode-specific. No assertion is deleted, skipped or xfailed.
