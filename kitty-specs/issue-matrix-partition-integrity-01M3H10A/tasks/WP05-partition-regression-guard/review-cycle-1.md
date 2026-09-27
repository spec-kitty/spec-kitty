---
affected_files: []
cycle_number: 1
mission_slug: issue-matrix-partition-integrity-01M3H10A
reproduction_command:
reviewed_at: '2026-09-27T11:53:42Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback (cycle 1) — reviewer-renata

What is good: counterfactual verified (planning-base scan reports review raw-path + discovery-dir-read + bypass, merge discovery-dir-read + bypass + missing terminality fn, doctrine `cat` at SKILL.md:593); fail-closed on missing file / missing Gate-4 section / renamed function is real; 21/21 pass; ruff, ruff format, mypy clean.

**Issue 1 (blocking — FR-008 / NFR-001 / SC-005): the guard does not cover the live matrix-read sites of the fixed code, so the defect class (primary partition fed to the matrix read) can re-enter unguarded.**
The `discovery-dir-read` rule only inspects `load_issue_matrix` / `issue_matrix_artifact_present` / `validate_issue_matrix` called with a bare `feature_dir`-like Name. After WP03/WP04 those readers are reached through wrappers and the name-based `RESOLVED_MATRIX_NAMES` carve-out, so the rule no longer sees them. Each mutation below was applied to the current lane-e source and `scan_python` reported **zero** violations:
1. `merge_gates.py` terminality gate: `feature_dir_for_blocker = coord_matrix_source` -> `= primary_discovery_dir` (the exact #4943 wrong-partition shape).
2. `merge_gates.py` completeness gate: `_load_issue_matrix_rows(coord_matrix_source)` -> `_load_issue_matrix_rows(primary_discovery_dir)`.
3. `review/__init__.py` `review_mission`: `matrix_dir = matrix_source` -> `matrix_dir = _primary_discovery_dir`.
4. `review/__init__.py` `review_mission`: `_evaluate_issue_matrix(..., matrix_dir=matrix_dir, ...)` -> `matrix_dir=feature_dir`.
Each is a direct working-tree read of the primary issue-matrix (what NFR-001 says must count), and the helper is still called, so `bypass` does not fire either.

How to fix (suggested; any equivalent is fine):
- Treat the wrappers as matrix readers with their matrix-location argument: `_load_issue_matrix_rows` (arg 0), `_issue_matrix_approval_blocker` (arg 0, when not in the ref-content arm), `_evaluate_issue_matrix` (`matrix_dir=` kwarg). Flag any of these fed a `DISCOVERY_DIR_NAMES` value.
- Flag assignment of a `DISCOVERY_DIR_NAMES` value to a `RESOLVED_MATRIX_NAMES` name (or to `feature_dir_for_blocker`), allow-listing precisely the documented cases (the `matrix_dir if matrix_dir is not None else feature_dir` legacy fallback in `_evaluate_issue_matrix`, and the decorative `feature_dir_for_blocker = primary_discovery_dir` in the `isinstance(..., str)` arm) — pin each allow-listed site so the carve-out cannot widen silently.
- Add the four mutations above to `TestSelfMutation` so the non-vacuity check covers the partition-swap class, not only the historical line shapes.

**Issue 2 (non-blocking, fold if cheap): doctrine prohibition carve-out is line-wide.** `_PROHIBITION_RE` searches everything before the span on the line, so `Never skip this step: run \`cat kitty-specs/s/issue-matrix.json\` first.` passes. Tighten to a prohibition immediately governing the span (e.g. "Do NOT"/"never" within the same clause, a few words before it) and add that sentence as a negative case in `test_prohibition_span_is_not_a_violation`.

**Issue 3 (nit):** `scan_doctrine` recomputes `text.splitlines()` per line (O(n^2)); compute offsets once.
