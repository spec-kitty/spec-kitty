# Tracer: Approach

Mission: `accept-fail-closed-missing-lanes-01M3CC1V` — fix P0 #4891.

## Plan of attack

1. **Red-first (ATDD, C-001/ADR 2026-07-17-1).** Land a failing repro through the real accept
   path *before* the fix. Two red anchors:
   - Invert the existing characterization test that *codifies* the bug:
     `tests/characterization/test_trio_pure_cores.py::test_missing_lanes_manifest_is_a_silent_noop`
     → assert fail-closed diagnostics (template: the sibling `test_corrupt_lanes_json_blocks_and_skips_all_checks`).
   - Add an issue-pinned `@pytest.mark.regression` case asserting `summary.ok is False` +
     recorded blocked/skipped checks when `lanes.json` is absent (unit level on
     `_resolve_lanes_manifest_or_stop` / `collect_feature_summary`).
2. **Fix (single seam).** In `_resolve_lanes_manifest_or_stop` (`acceptance/gates_core.py`),
   when `read_lanes_json` returns `None` (genuine absence), mirror the `CorruptLanesError` arm:
   append an `activity_issue` (the field that flips `AcceptanceSummary.ok`), a `blocked_checks`
   `lanes_manifest` diagnostic, and `_append_skipped_lane_checks(..., include_matrix_presence=True)`.
   Use `MissingLanesError`-style remediation wording (finalize-tasks / doctor mission-state --fix).
3. **Green + regression guard.** Confirm the red tests pass; confirm present-lanes and
   corrupt-lanes cases unchanged; add an e2e `summary.ok is False` assertion in
   `tests/cross_cutting/misc/test_acceptance_support.py`.
4. **Blast-radius watch.** Keep coord golden paths green
   (`tests/integration/test_accept_matrix_coord_partition.py`,
   `test_placement_partition_golden_path.py`); confirm the orchestrator-readiness consumer
   (`orchestrator_api/commands.py`) is not broken.

## Targeted test surface (per charter Testing Requirements)

- `tests/characterization/test_trio_pure_cores.py`
- `tests/cross_cutting/misc/test_acceptance_support.py`
- `tests/integration/test_accept_matrix_coord_partition.py`, `test_placement_partition_golden_path.py`
- any `tests/specify_cli/**` accept/acceptance module that grep surfaces
