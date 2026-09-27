---
affected_files: []
cycle_number: 1
mission_slug: accept-fails-closed-01M3HS4V
reproduction_command:
reviewed_at: '2026-09-27T18:29:00Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review — cycle 1 (reviewer-renata): CHANGES REQUESTED

The gate fix itself is correct and the #4974 tests prove it: mutations for "write judged over fresh", "judge the pre-lock matrix", "drop the FR-010 guard" and "silent gate lock timeout" each turn a 4974 test red. 462 passed / 6 skipped on the targeted set. Ruff is clean. The mypy errors match the ab8ce067 baseline (3). The format drift in `__init__.py` and `test_acceptance_cores.py` was already there on the base (13 and 11 hunks, unchanged). The edits to the pre-existing tests keep their assertions meaningful.

What blocks approval: three new FR-010 branches in `_stamp_acceptance_record` (`src/specify_cli/acceptance/__init__.py` ~L1593-1644) have no test at all. Each of these mutations left the whole targeted set GREEN:

**Issue 1 — the planning-artifact-only bypass is untested (squad fold).** I replaced the bypass (`record_acceptance(...); return` when `acceptance_matrix_gate_skip_reason == PLANNING_ARTIFACT_ONLY_SKIP_REASON`) with `raise AcceptanceError`. Nothing failed. The existing planning-only accept tests (`test_acceptance_regressions.py::test_accept_cli_no_commit_json_allows_planning_artifact_research_without_matrix`, `test_canonical_acceptance.py`) use `--no-commit` or `collect_feature_summary` only, so they never reach the stamp. If this branch broke, no planning-artifact-only mission could be accepted and no test would notice. Fix: add a stamping accept test (auto-commit, not `--no-commit`) for a planning-artifact-only mission that asserts exit 0 and that `accepted_at` is set.

**Issue 2 — the fail-closed path for any other `acceptance_matrix_dir is None` is untested.** I replaced the `raise AcceptanceError("Cannot record acceptance: ...")` with a silent `record_acceptance(...)`. Nothing failed. Fix: add a unit test that calls `_commit_acceptance_meta` / `perform_acceptance` with an ok summary, `acceptance_matrix_dir=None` and `acceptance_matrix_gate_skip_reason=None`. Assert that it raises `AcceptanceError` and that meta.json has no `accepted_at`. Also cover a non-planning skip_reason value if you keep the string compare.

**Issue 3 — the guard's lock-timeout translation is untested (squad fold).** I changed `except FeatureStatusLockTimeoutError` in `_stamp_acceptance_record` so it no longer catches the timeout. Nothing failed. SC-006 only exercises the gate-side timeout, because the gate fails first. Fix: add a test where the gate succeeds and the guard then times out, for example by patching `specify_cli.acceptance.matrix.locked_acceptance_verdict_guard` with a context manager that raises `FeatureStatusLockTimeoutError`, or by holding the lock from another thread with a short timeout only around the stamp. Assert that `accept` exits non-zero with the "lock timed out while recording acceptance" diagnostic and that there is no `accepted_at`.

**Issue 4 (minor, non-blocking) — the proof is not in the Activity Log.** The WP prompt asks for two things in the WP02 Activity Log: the half-by-half proof and adding NFR-001 to the refs. Both currently live only in the fd25049d commit message. Please add an Activity Log entry.

No production-code changes are requested. This round only needs tests (plus the log entry). Re-run the same targeted set.
