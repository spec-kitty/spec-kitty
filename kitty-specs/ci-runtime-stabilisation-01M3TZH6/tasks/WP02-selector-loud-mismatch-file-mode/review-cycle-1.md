---
affected_files: []
cycle_number: 1
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T09:55:47Z'
reviewer_agent: claude-reviewer
wp_id: WP02
---

# WP02 review feedback (cycle 1, reviewer-renata)

Verified: red-first commit 4c00016489 fails at collection on the base (ImportError: `BatteryPartition`), tip green (tests/ci 93 passed; test_module_length_agreement 20 passed; test_module_shard_registry 18 passed; make test-fast 2172 passed / 5 skipped). ruff check, ruff format --check, mypy --strict, C901 and `derive_pinning_inventory.py --check` are all clean. The enumeration smoke gives 235. No live callers of the removed `positional_weights` remain, and the WP01 characterization oracle is unchanged. Three items block approval. Each has a small fix.

1. **tests/architectural/test_module_length_agreement.py:402-409: a misplaced decorator strips the tier marker from an existing ratchet test.**
   - Problem: the new test `test_consumer_marker_is_the_shared_selector_constant_not_a_copy` now carries `@pytest.mark.fast` twice, while `test_allowlist_does_not_exceed_baseline` lost the `@pytest.mark.fast` it had on the base. I verified this with `pytest tests/architectural/test_module_length_agreement.py --collect-only -m fast`: the shrink-only ratchet test is no longer selected (16/20 collected).
   - Required fix: drop the duplicate decorator on the new test and restore `@pytest.mark.fast` directly above `def test_allowlist_does_not_exceed_baseline`. Do not touch lines 1-93.

2. **tests/ci/test_shard_select.py (file-weights tests, around the `resolve_file_weights` section): the median rule is not pinned.**
   - Problem: a mutation probe in `scripts/ci/shard_select.py` `resolve_file_weights` that replaces `statistics.median(known.values())` with `statistics.mean(...)` survives the whole file (78 passed). Every test uses known sets where the median equals the mean ({10, 30}, {2, 4}, a single value). The WP contract requires the median, never another statistic.
   - Required fix: add a fast test with a skewed known set, for example `resolve_file_weights(["a.py","b.py","c.py","d.py"], {"a.py": 1.0, "b.py": 2.0, "c.py": 100.0})`. It must assert that `d.py` gets `2.0`, where the mean would give 34.33.

3. **scripts/ci/shard_select.py:392 (`_print_battery_parts`): file-granularity loudness is never exercised through a caller.**
   - Problem: a mutation probe that deletes `report_mismatch(result.resolution, label="battery")` survives (78 passed). `test_battery_parts_cli_prints_each_part_with_its_file_count_and_load` times every non-roster file, so no mismatch ever occurs. FR-005 requires loud reporting in both granularities. Today only the module-row path is proven loud end-to-end.
   - Required fix: add a CLI case with a missing file and/or a stale timing key. With `GITHUB_STEP_SUMMARY` pointed at tmp_path, assert exactly one `::warning title=shard timings::battery:` line on stdout and exactly one appended summary line. Also assert that the agreeing case, which the existing test covers, prints no warning.

## Non-blocking notes

- WP14 (`WP14-battery-timings-seed-and-budgets.md` around line 320) documents `battery-parts --registry … --timings … --root .`. Your CLI takes `--path/--deselect/--roster/--timings/--shards/--root`. WP14 already has a fallback ("or the equivalent `battery_parts(...)` call"), and WP05 and WP06 consume the library functions directly, so C-010 holds: there is one enumeration and one LPT. Still, record the deviation and its rationale (YAML stays out of the stdlib module) in the WP02 Activity Log so WP14 adapts its invocation.
- The Activity Log has no implementer entry. Record the manual enumeration smoke result there (235 on this tip).
- `report_mismatch` flattens only `\n` in the summary line. A `\r` inside a reason would pass through. This is cosmetic.
- Removing `test_positional_weights_does_not_alias_the_input_list` is justified, because the weights are now an immutable tuple.
