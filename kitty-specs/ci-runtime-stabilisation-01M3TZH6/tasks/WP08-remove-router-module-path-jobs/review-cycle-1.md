---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T12:57:40Z'
reviewer_agent: claude-reviewer
wp_id: WP08
---

# WP08 review — cycle 1 (reviewer-renata): changes requested

What I verified holds and must stay as it is:
- Red-first: `test_router_runs_no_module_owned_test_tree` at 16f17b92a2 (parent e292e3513c is WP07's tip plus the lane-a merge) is red with exactly `{'tests-consolidation': [('tests/consolidation','consolidation')], 'tests-status': [('tests/status','status')], 'tests-cli': [('tests/cli','cli')]}`, and green at the tip.
- Mutations: re-adding `tests-status` reds the guard, `test_removed_duplicate_router_job_stays_absent[tests-status]` and the existing duplicate-set gates. Re-adding it under a new name reds the guard.
- `router gate` keeps its name and the needs set-equality pin is green. The pinning inventory is fresh (`--check` 0) and the regeneration matches the +3 import lines. The guard uses `shard_select.resolve_module_test_dirs` (C-010) in one self-contained, marked-temporary block.
- The out-of-map commits a3c17e36e6 and 59a1a92567 are small and justified.
- Targeted architectural tests: 198 passed, 1 skipped. `tests/ci`: 116 passed. `make test-fast`: 2172 passed. ruff, format and `bash -n` are clean. mypy adds no new errors (the 4 errors in `test_ci_module_wiring.py` are already on the base).

**Issue 1 — The T037 tests break the `fast` marker contract and add per-PR runtime (blocking)**
- File: `tests/ci/test_ci_module_wiring.py:392-443`. The module carries `pytestmark = pytest.mark.fast` at line 49.
- Problem: `_collect_node_ids` spawns `pytest --collect-only` over 3 trees of about 3,700 tests. The two T037 tests do 4 such collections, about 7.7 s per test (15.5 s in total). `pytest.ini:57` defines `fast` as "pure-logic tests with no subprocess/git overhead (sub-second per test)". The `ci` module row runs `tests/ci` on every `scripts/ci/**` and `.github/workflows/**` PR, under coverage. That is a marker misclassification plus a per-PR runtime cost, in a mission whose goal is CI runtime. The WP scoped T037 as collect-only evidence recorded in the Activity Log ("Files: none edited").
- Required fix: remove the subprocess collections from this `fast` module. Either:
  - (a) keep only the cheap structural pins (each nightly gate's `paths == []`, `ignores == []` and `marker_expr`, plus the item in Issue 2) and record the collect-only counts in the Activity Log and PR body, as the WP asks; or
  - (b) move the collect-based checks to a file that is not marked `fast` (out-of-map, with a one-line rationale).

**Issue 2 — The performance-home test asserts a tautology and does not pin what makes the tests run (blocking)**
- File: `tests/ci/test_ci_module_wiring.py:433-443`.
- Problem 1: line 439 asserts `gate.marker_expr == "performance"`. Line 442 then re-collects with `-m gate.marker_expr`, the identical selection, so `set(performance_in_trees) <= nightly` at line 443 is always true. It would pass on a do-nothing change.
- Problem 2: the test does not check `SPEC_KITTY_RUN_PERFORMANCE: "1"` on the nightly `performance` job (`ci-nightly.yml:121`). That variable is what actually executes the 7 tests; without it they are skipped, exactly as they were in the router. So the "homed" claim is not pinned.
- Required fix: delete the tautological re-collect and subset assertion. Assert instead that the nightly `performance` job's env sets `SPEC_KITTY_RUN_PERFORMANCE` to `"1"`. That check reads the workflow YAML and needs no subprocess.

**Issue 3 — The stress-set pin is an exact equality, so any new stress test reds it (fix together with Issue 1)**
- File: `tests/ci/test_ci_module_wiring.py:424`.
- Problem: `sorted(in_removed_trees) == sorted(_STRESS_NODES_FROM_REMOVED_ROUTER_JOBS)` turns red whenever anyone adds a stress test under `tests/status`, `tests/cli` or `tests/consolidation`. That would be a false red in an unrelated suite, with a message ("update T037's record") that points at a closed WP.
- Required fix: if any collect-based check survives (option b), assert that the nightly selection contains the two known node-ids (a subset), not that the set is exactly those two.

**Issue 4 — A comment will point at a guard the closeout fold deletes (non-blocking; fix while you are there)**
- File: `tests/ci/test_ci_module_wiring.py:366-369`.
- Problem: the comment says re-adding the duplicate under a new name "is red in tests/architectural/test_no_duplicate_suite_execution.py". The post-consolidation orchestrator fold removes that guard, after which the comment is false.
- Required fix: refer to "the FR-010 cross-job uniqueness live check (WP15)" instead, or say that the directory guard is temporary.
