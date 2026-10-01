---
affected_files: []
cycle_number: 2
mission_slug: ci-runtime-stabilisation-01M3TZH6
reproduction_command:
reviewed_at: '2026-10-01T10:29:05Z'
reviewer_agent: claude-reviewer
wp_id: WP02
---

# WP02 review feedback (cycle 2, reviewer-renata)

All three cycle-1 items are fixed. I checked each one with its mutation:

- **median → mean:** caught by `test_file_weights_fill_is_the_median_not_the_mean_of_a_skewed_known_set`.
- **Deleting the battery `report_mismatch` call:** caught by `test_battery_parts_cli_is_loud_on_a_file_timing_mismatch`.
- **Cycle-1 duplicate-marker state:** `-m fast` drops to 16, and `test_allowlist_does_not_exceed_baseline` disappears from the selection.

The `-m fast` node list on the tip equals the planning base (`f28a43cdae`, 16 nodes) plus exactly `test_consumer_marker_is_the_shared_selector_constant_not_a_copy` (17 nodes).

Results on the tip:

| Check | Result |
|---|---|
| `tests/ci/test_shard_select.py` + `test_capture_shard_timings.py` | 96 passed |
| `tests/ci` | 1098 passed |
| `test_module_length_agreement.py` + `test_module_shard_registry.py` | 38 passed |
| `make test-fast` (env var not exported) | 2172 passed / 5 skipped |
| ruff check, ruff format --check, mypy --strict, C901 | clean |
| `derive_pinning_inventory.py --check` | rc=0 |
| Enumeration smoke | 235 |

Red-first is confirmed: the tip test file fails on the base with `ImportError: BatteryPartition`.

One reviewer-chosen mutation survives, and it is the same class as cycle-1 item 2/3, so it blocks.

1. **scripts/ci/shard_select.py:216 (`resolve_file_weights`, `if missing or stale:`): stale-only loudness is not pinned.**
   - **Problem:** I replaced `if missing or stale:` with `if missing:`. The mutation survives `tests/ci` and `test_module_shard_registry.py` (1116 passed). With that change, a timings file whose only defect is stale keys gives `reason=None`. The partition then reports "agreeing" and nothing is printed. Every existing test that has stale keys also has a missing file:
     - the T006 example;
     - `test_file_weights_median_ignores_stale_keys`;
     - `_battery_inputs`, which `test_battery_parts_reports_the_weight_resolution_loudly_inputs` builds on;
     - the new CLI test.

     So the `stale` half of the condition is never exercised on its own. This is the routine post-deletion state (for example #5503 deleted a battery file). FR-005 and the WP objective ("missing and stale keys are reported loudly") require it to be loud.
   - **Required fix:** add a fast test where every file in `files` is timed and there is at least one extra key. For example, `resolve_file_weights(["a.py", "b.py"], {"a.py": 1.0, "b.py": 2.0, "gone.py": 5.0})` should assert:
     - `resolution.mismatch` is true;
     - `stale == ("gone.py",)` and `missing == ()`;
     - the weights are unchanged, `(1.0, 2.0)`.

     Preferably also cover it through the CLI or `report_mismatch`: exactly one `::warning title=shard timings::battery:` line that names `gone.py`. Do not change production code. It is correct; only the pin is missing.

## Non-blocking (carried over from cycle 1, still open)

- The WP02 Activity Log still has no implementer entry. Please record two things there:
  - the `battery-parts` CLI signature deviation (`--path/--deselect/--roster/--timings/--shards/--root` instead of WP14's documented `--registry …`, because YAML stays out of the stdlib module), so WP14 adapts its invocation;
  - the enumeration smoke result (235 on this tip).
