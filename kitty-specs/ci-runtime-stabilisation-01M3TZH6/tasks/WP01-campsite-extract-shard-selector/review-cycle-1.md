---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T09:17:29Z'
reviewer_agent: claude-reviewer
wp_id: WP01
---

# WP01 review feedback (cycle 1) — reviewer-renata

Verified OK: red-first commit ea46ab0b21 fails on its parent with `ModuleNotFoundError: No module named 'scripts.ci.shard_select'`; tip is green (tests/ci 153 passed; the five architectural gate files 154 passed, 1 skipped; length-agreement -m fast 16 passed); ruff check, ruff format --check, mypy --strict (per file) and derive_pinning_inventory --check are clean. The algorithm is behaviour-preserving: an independent real-collection cmp of old heredoc vs new CLI is identical for kernel 1/1, next 1/2 and 2/2, glossary 1/1, status 1/2 and 2/2. The runner step is unchanged.

## Blocking

1. **tests/ci/test_shard_select.py:59-64 and :88-110: the characterization does not exercise production `positional_weights` (scripts/ci/shard_select.py:96-104).**
   - Problem: the row and mismatch tests build weights with the test-local `_positional_items`, which copies the fallback. `_select_module` (the path `module-tests.yml` runs) uses `positional_weights` instead. I mutated `positional_weights` to always return uniform weights, which throws away the measured timings for every module row and reshuffles every shard. All 63 tests in test_shard_select, test_capture_shard_timings and test_module_shard_registry still passed. The WP names a silent module-row reshuffle as its only real risk, and that risk is unguarded.
   - Required fix: build the `lpt_assign` side of the row and mismatch characterizations from `positional_weights(node_ids, durations)`. Keep the frozen oracle independent. Also add a direct test: equal lengths return the durations unchanged, and a length mismatch returns `[1.0] * len(node_ids)`.

2. **scripts/ci/shard_select.py:107-185: the production CLI path has no committed test.**
   - Scope: `main`, `_select_module`, `resolve_module_test_dirs`, `_load_durations`, `_parse_shard`, both exit-64 `::error::` paths and the output format.
   - Evidence: three more mutations survived all tests: dropping the `os.path.isdir` filter in `resolve_module_test_dirs`, adding a trailing newline to `shard_tests.txt`, and changing `EXIT_NO_TESTS` from 64 to 0. Right now the one-off T003 `cmp` is the only proof of equivalence, and it is not committed. That breaks the review brief rule "production path tested, not only helpers" and the CLAUDE.md rule "every new branch/helper needs tests in the same PR".
   - Required fix: add tests to tests/ci/test_shard_select.py for each of the following.
     - `resolve_module_test_dirs`, using `tmp_path` and `monkeypatch.chdir`, covering three cases: empty JSON falls back to the `tests/<module>` mirror; declared dirs keep only those that exist; neither exists returns `[]`.
     - `main([...])` end to end with `subprocess.run` stubbed, or `--python` pointed at a tiny stub that prints node ids. Assert:
       - `--out` content is byte-exact, newline-joined with no trailing newline, and equals the frozen oracle's selection;
       - the final stdout line;
       - a missing `--timings` file falls back to uniform weights;
       - both exit-64 `::error::module-tests: …` paths (no test dir; zero collected).

## Non-blocking

3. The T004 marker pin landed in the feat commit, not in the red commit. That is acceptable: the WP Test Strategy places T004 in the green phase. I also checked that the new `test_capture_selects_with_the_shared_marker_constant` FAILS against the base `capture_shard_timings.py`, so the test is not vacuous. Next time, commit the failing pin first for any behaviour change.
4. The Test Strategy's combined `mypy --strict scripts/ci/shard_select.py scripts/ci/capture_shard_timings.py` exits 2 with "Source file found twice under different module names". This is caused by how the command is written, not by the code: each file passes alone, and both pass with `--explicit-package-bases`. Record the working command in the PR's Tests run section.
