# Issue matrix — ci-status-audit-path-literal-routing-01M6EK04

One row per issue referenced in spec.md. `in-mission` = fixed by a WP in this mission (non-terminal; must
reach `fixed` / `verified-already-fixed` / `deferred-with-followup` before mission `done`).

| Issue | Title | Verdict | Evidence ref |
|-------|-------|---------|--------------|
| #6879 | ci: a src/specify_cli/status/** diff does not route tests/audit/** | in-mission | WP01 (candidate fix 1): new `path_literal_audit` group + `tests-path-literal-audit` job running `tests/audit/test_no_legacy_path_literals.py`; pinned by `tests/ci/test_path_literal_audit_routing.py`. Candidates 2/3 and the #6516 allowlist drain stay out of scope (spec C-001/C-002). |

Valid `Verdict` values: `fixed`, `verified-already-fixed`, `deferred-with-followup`, `in-mission`.
