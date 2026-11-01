# Approach — doctor-decisions-duplicate-openings-01M66YMR (#6764)

- **[2026-10-30][specify] Approach: report the tolerated duplicate openings from the existing fold rather than adding a detector.** The issue asks for an informational finding; the cheapest honest implementation is one exported helper in `specify_cli/decisions/index_fold.py` that reuses the fold's own equality rule, consulted inside the per-decision loop the read-only diagnose path already runs.

- **[2026-10-30][tasks] Work-package shape changed from two to three during implementation.** WP02 was drafted as a docs package owning `docs/api/cli-commands.md`; that file's command sections are generated from the help body in `src/specify_cli/cli/commands/doctor.py`, which a `planning_artifact` package may not own. `finalize-tasks` refused the re-classification (`LANE_MEMBERSHIP_FROZEN`), so WP03 (`code_change`) was added for the help body + regenerated reference and WP02 kept the changelog. The analysis report was re-recorded (revision 2) before WP03 could be claimed.

- **[2026-10-30][review] Review stayed proportionate: one reviewer pass per WP over the integrated diff, the WP prompt's eight-item anti-pattern checklist, and the module-level test suites.** No adversarial squad for a ~60-line additive report field; the behaviour is fully covered by four red-first CLI tests.
