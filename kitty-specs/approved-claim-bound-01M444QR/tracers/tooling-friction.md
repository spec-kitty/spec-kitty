# Tooling friction

Append-only notes for mission `approved-claim-bound-01M444QR`.

- 2026-10-04 (plan): `mission create` committed `meta.json` and `tasks/README.md` itself; `spec-commit` was used for the grounding document before the spec existed and accepted it.
- 2026-10-04 (implement): editing `tasks.md` or a WP prompt after `record-analysis` makes the analysis report stale, and `agent action implement` then refuses a re-claim (`stale_analysis_report`); re-recording the report clears it. Review verdict files are written with `--no-auto-commit`, so the orchestrator commits them after every review.
- 2026-10-04 (implement): the dead-symbol gate needs a `src/` caller for every exported name, so a work package that defines an API for later parallel packages is red on its own lane until they land.
- 2026-10-05 (implement): the lane commit guard warns `ACTIVE_WP_SCOPE_VIOLATION` for every out-of-map file; it never blocked.
