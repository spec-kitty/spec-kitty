---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T09:42:26Z'
reviewer_agent: claude-reviewer
wp_id: WP13
---

# WP13 review — cycle 1 — REJECT (reviewer-renata)

Red-first, caching design, mutation non-vacuity, finalizer, ruff/format and the before/after
timings all check out (details at the end). One blocking defect remains. The new FR-006
tests leave **synthetic findings in the per-file memo under the REAL cache key**. Any real
consumer that runs after them in the same process is then served the fake world, and the
real gate goes **false-green**. FR-006 requires that caching works "without weakening any
gate". WP13's own risk table also requires order independence ("every new test clears
first, and the module fixture clears last"). Clearing first protects the new test, but it
does not protect the consumers that run after it.

## Blocking

1. **tests/architectural/test_clock_call_ban.py:542-552** (`test_real_scan_pair_scans_each_file_once`)
   - **Problem.** The test runs the real consumers with `_violations_for_file` faked to
     return `[]`. That fills `_tree_call_sites` under the real key
     `(scan.REPO_ROOT.resolve(), tuple(scan.iter_python_files()))` with an EMPTY scan, and
     the test leaves that entry in the cache. Every later real-tree consumer in the file is
     then served "no violations".
   - **Reproduced on the tip** (scratch checkout of 916fad9492), with a planted
     `src/specify_cli/_wp13_review_probe.py` containing `datetime.datetime.now()`:
     - `pytest …::test_no_banned_wall_clock_call_outside_the_door` alone: **FAILED** (correct).
     - `pytest …::test_real_scan_pair_scans_each_file_once …::test_no_banned_wall_clock_call_outside_the_door`:
       **2 passed in 0.77 s**, which is a false green on a real violation.
   - **Why it matters.** Any reordering triggers this: explicit node ids, `--ff`/`--lf`/`--sw`,
     a future random-order plugin, or test moves.
   - **Required fix.** Leave the memo empty when each new test ends. Use either:
     - a function-scoped fixture used by the FR-006 tests that calls `cache_clear()` before
       AND after the test (yield fixture), or
     - `try/finally: _tree_call_sites.cache_clear()`.

     Apply the same to `test_tree_call_sites_scans_once_per_root_and_rescans_a_new_root`
     (:497) and `test_tree_call_sites_returns_an_immutable_value` (:522). They key on
     tmp roots, so they are harmless today, but keeping all of them consistent removes the
     hazard class.

2. **tests/architectural/test_interpreter_shard_coverage.py:823-845 and :847-861** (`test_mutation_controls_bypass_the_memo`, `test_real_consumers_collect_each_selection_once`)
   - **Problem.** Both tests warm `_collect_memo` under the REAL key
     `(REPO_ROOT.resolve(), <real shard/full-selection paths, ignores, marker>)` with the
     synthetic `_consistent_fake_world()`, and leave it there. :805 does the same for its
     two literal keys.
   - **Reproduced on the tip.** This command took **3 passed in 0.40 s**:

     ```
     pytest …::test_mutation_controls_bypass_the_memo …::test_no_shard_collects_zero_tests …::test_shard_union_equals_full_selection_with_zero_gap_and_zero_overlap
     ```

     The two real consumers normally take about 35 s + 24 s. Here they were judged against
     the synthetic disjoint world, so the FR-004/FR-005 coverage gate can pass vacuously.
   - **Required fix.** Same as item 1. Clear `_collect_memo` after (and before) each of the
     three FR-006 tests, using a yield fixture or `try/finally`.

3. **Pin the fix (non-vacuity of the fix itself).**
   - **Required.** Add one assertion per file showing the memo is empty after a FR-006 test.
     Either:
     - assert `cache_info().currsize == 0` from the fixture's teardown path, or
     - add a small test that invokes the production-path test function and then asserts
       `currsize == 0`.
   - **Check before resubmitting.** Re-run the two ordering commands above. With the planted
     offender, the clock pair must go red, and the shard triple must take the real
     collection time.

## Verified OK (no action)

- **Red to green.**
  - The 9 new tests fail on 2a6ce72ce8, whose parent is the base bf8e66b232: `NameError`
    for the missing helpers, and the finalizer test fails because the fixture is absent.
  - On the tip: shard 21 passed, clock 26 passed, clock-import 10 passed,
    manual-global-state 44 passed, dead symbols 37 passed, allowlist contract 4 passed.
- **Mutation probes on the tip** (each failed as required):
  - broken overlap detection: the duplicated-file control reds;
  - the zero-test consumer bypassing the memo: the production-path test reds;
  - the union consumer bypassing the memo: reds;
  - the default `collect` pointed at the memo: `test_mutation_controls_bypass_the_memo` reds;
  - the clock consumer bypassing the memo: `test_real_scan_pair` reds;
  - the partition returning `[]`: `test_stale_exemption_removal_reds_the_gate` reds;
  - the root guard removed: the refusal test reds.
- **Memo design.** Keys hold no `gate.job` and no mutable objects, and values are tuples.
  The module-scoped autouse clears are in all three files. The dead-symbol finalizer only
  ever clears a stub inside its test, and `_walk_modules` still runs once per file
  (82 s vs 81.6 s on the base).
- **Lint and types.** `ruff check` and `ruff format --check` are clean. The 3 mypy errors
  at test_interpreter_shard_coverage.py:357 are identical on the base (:342), so they are
  pre-existing.
- **Scope.** `test_no_dead_symbols.py` is in `owned_files` on the planning base (D-37).
  Note that the lane's copy of the WP13 prompt is still the stale two-file version.

## Non-blocking

- **Pre-existing mypy errors.** #1928 is an open umbrella for strict-mypy debt, but it holds
  no record of this specific failure. To meet the Pre-existing Failure Reporting Rule,
  either add a comment on #1928 or open a dedicated issue. It should give the command, the
  three `Gate.replace(**dict[str, object])` arg-type errors in `_scratch_gates_with`, and
  the proof that they are on the base.
