---
affected_files: []
cycle_number: 1
mission_slug: merge-seam-test-isolation-campsite-01M3F61E
reproduction_command:
reviewed_at: '2026-09-26T17:52:04Z'
reviewer_agent: claude-reviewer
wp_id: WP01
---

# WP01 review feedback (cycle 1) - reviewer-renata / claude-reviewer

**Verdict: CHANGES REQUESTED.** The detector and shards are strong. Four fixes are needed before this gate governs 8 sweep WPs. All four are in WP01-owned files and are small.

## What was verified and is correct (keep it)
- RED is real through the entry point. At dbd46d04a3, in a temp worktree, `test_no_unallowlisted_sites` fails with 278 actionable `path:line in qualname: form mutates kind - use ...` lines.
- The census is 471 sites / 155 files / 278 keys. scanned_files is 3355, which is >= 3000. An uncontended scan takes about 4.0 s.
- Every shard's `owns:` matches `research/sweep_shards.tsv` exactly, and site totals per shard also match. The classes are transitional 434 / process-bootstrap 6 / subprocess-entry 13 / leak-sentinel 2 / deferred 16 = 471. The 5 deferred files are the C-002 set.
- The YAML has no line keys, and `test_ratchet_positional_anchor_ban.py` is green. No ratchet-owned file was touched. The coexistence gates are green (135 passed).
- ruff check, ruff format, C901 and mypy --strict are all clean.
- I probed 20 further forms: rebind, rebind-del, annassign, tuple-target, fchdir, unsetenv, `from sys import path`, `import sys as _s`, delattr, slice-del, `os.environ |=`, `setattr(os,"environ")`, `del os.environ["SPEC_KITTY_HOME"]`, nested import, and `import os.path`. All were caught correctly, and MonkeyPatch.context was correctly ignored.
- I planted a manual `os.chdir` in a new test file. The gate failed with an actionable message. I reverted it and the lane is clean.

## Required changes

1. **The gate imports `_home_pin_scan` and adds a new suppression (contract, R6, T002, NFR-006).** `test_coexists_with_home_pin_and_sys_modules_gates` does `from tests.architectural import _home_pin_scan  # noqa: F401` and asserts `scan_module.scan is not None`, which is vacuous.
   - The contract says the gate "does not import `_home_pin_scan`", and NFR-006 requires zero new suppressions.
   - Consequence (verified): `test_home_pin_seam_no_second_copy.seam_consumers()` now lists `tests/architectural/test_no_manual_global_state_mutation.py` as a seam consumer. That subjects the gate to the second-copy ban and the verdict-seam signals, which is exactly the design R6 avoided.
   - Fix: delete this test. Coexistence is proven by running those gate modules, which the Activity Log already records.

2. **The wall-clock assertion sits in an `architectural` module (T005 step 5, #2032 anti-pattern).** `test_scan_cost_budget` asserts `< 10.0 s` on a scan that takes about 4 s uncontended, in a module that runs under `-n auto`.
   - House convention (`test_spec_kitty_home_pin_budget.py` docstring) puts wall-clock assertions only in a module marked `pytestmark = pytest.mark.timing` and run `-n0`.
   - The WP said "Do not add a flaky wall-clock assertion". The test also re-scans the tree, adding about 4 s to every gate run.
   - Fix: remove it and record the measurement in the Activity Log. Alternatively, if the orchestrator extends ownership, move it to a separate `timing`-only module.

3. **The allowlist loader silently discards data, which is a vacuity hole in an exact, shrink-only gate.** `load_allowlist` does `rows[key] = row` (last one wins) and `owns_by_shard[shard] = owns` (overwrite).
   - Verified: one shard holding `{a.py,f,cwd,count 5}` and `{a.py,f,cwd,count 2}` with a live count of 2 produces **no** verdict. The stale row escapes under-count.
   - Verified: two YAML files that both declare `shard: S1` silently lose the first file's `owns:`.
   - Fix:
     - Fail on duplicate `(file, qualname, kind)` keys, whether in one shard or across shards.
     - Fail on duplicate `shard:` names.
     - Assert that `shard:` equals the file stem.
     - Add in-memory or tmp_path self-mutation tests for each case.

4. **The over-count message is not actionable and gives wrong advice (FR-009).** `test_no_over_count` prints `allowlist under-states the live count (shrink is the only valid edit): [(key, actual, allowed)]`.
   - Actual > allowed means a new manual site appeared. The fix is to convert that site, and "shrink" is wrong advice.
   - Fix: for each over-count key, list the live sites as `path:lineno in qualname: form mutates kind - use <replacement_for(kind)>`, reusing the per-site formatter. Include "convert the new site; do not raise `count`".

## Non-blocking (fix if cheap, otherwise note it in the tracer)

5. The SPEC_KITTY_HOME exclusion matches by **line**, not by node. Every os.environ hit on the same line as an owned write is dropped. Verified: `os.environ["SPEC_KITTY_HOME"] = os.environ.pop("OTHER")` yields 0 sites. The contract says "excludes exactly", so match on `(lineno, col_offset)` or on the node instead.
6. The `subprocess-entry` reason on `tests/architectural/untrusted_path_audit/audit.py::<module>` says "runs in a child process". The module is actually imported in-process by `test_untrusted_path_containment.py:68`, where its guarded insert does nothing under pytest. Reasons are per-class boilerplate. Consider site-specific reasons, as in the contract example, or leave re-classification to the S6 sweep.
7. Nit: the comment on `FIXTURE_DATA_EXCLUSIONS` is garbled ("Sites with no row anywhere in the allowlist are files/globs ...").
