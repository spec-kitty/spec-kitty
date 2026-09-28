---
affected_files: []
cycle_number: 1
mission_slug: exit-zero-data-intact-01M3KDAS
reproduction_command:
reviewed_at: '2026-09-28T12:18:41Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 review feedback (reviewer-renata), commit 96f66a77

What passed: the driver fix (FR-007), the single `is_assigned_mission_number` leaf, the unconditional target-tree write through the MERGE_BOOKKEEPING commit, and the read-back via `_read_committed_meta_json` are correct. Red-first is confirmed on a `git archive` base copy (8 of 18 new tests fail on base, including the sequential and hand-numbered consolidates). The accept-stamps-target-first fixture is realistic. The architectural gates pass (268 passed). ruff, format and C901 are clean, and mypy --strict shows only the 4 errors that already exist on base. The 46 consolidation test files pass (732 passed).

The items below are required changes.

## 1. `mission_number_baked` is still set BEFORE verification (plan D2(e) not met)
`src/specify_cli/consolidation/ordering.py:787` (`_bake_mission_number_into_mission_branch`) still calls `_mark_mission_number_baked` right after the mission-branch write. It is also called on the idempotency hits at `ordering.py:448` and `:621`. All of these run before `_verify_and_announce_mission_number`. Plan D2(e) lists "Setting the flag before verification" as a REJECTED alternative. On `--resume` the executor tries to compensate by re-reading the mission branch (`executor.py:~1514-1519`), but that read returns None on the coord-topology primary-tree fallback, where the mission branch carries no meta.json. It also returns None on any read failure. In those cases the run skips verification entirely and can exit 0 with a wrong or null number on the target. That is exactly the failure D2 rejects.
Required: set the flag only after `assert_mission_number_on_target` succeeds. For example, move `_mark_mission_number_baked(run.state, ...)` into `_verify_and_announce_mission_number` after the assert, and stop marking it in the bake/idempotency paths. Alternatively, make resume re-derive the expected number without depending on the mission-branch meta. Update the docstring NOTE at `ordering.py:~714`.

## 2. No resume test (T013-4 / D2e)
`tests/consolidation/test_mission_number_truthful_4900.py` contains no `--resume` test. The resume/fallback branch `executor.py:~1514-1519` and `baseline.read_mission_number_from_ref` are not executed by any test, which also puts NFR-005 (≥90% diff coverage) at risk.
Required: add a test in which the first run fails read-back (inject at `baseline._read_committed_meta_json`, as in the mismatch test). Then run `_run_lane_based_consolidation(..., resume=True)` or the CLI `--resume` without the fault. Assert that it re-verifies and records the correct number on the target, or that it exits non-zero. It must never exit 0 with null. Add a direct unit test for `read_mission_number_from_ref` too (assigned / null / unreadable ref).

## 3. FR-005 "matches the printed lines" is not asserted
`test_sequential_consolidates_record_1_then_2_on_target` and `test_hand_numbered_target_gives_next_mission_8` never check stdout. A mutation that deletes `console.print("[green]Assigned[/green] mission_number=...")` in `executor.py::_verify_and_announce_mission_number` passes all three consolidate tests (verified).
Required: capture output (capsys) and assert `Assigned mission_number=1` / `=2` / `=8` appears exactly once per run, after the number is recorded on the target.

## 4. NFR-003 remedy text and expected number not asserted in the mismatch test
`test_readback_mismatch_exits_nonzero_and_never_prints_false_assigned` asserts only `Error:` and `999`. The WP (T016.1) says "Tests assert the remedy text", and FR-006 requires that expected vs recorded both be named.
Required: also assert the expected number (`expected 1`), the `spec-kitty consolidate --mission <slug> --resume` remedy and the `git show main:kitty-specs/<slug>/meta.json` hint.

## 5. Regression marker not removed after green (T018)
`tests/consolidation/test_mission_number_truthful_4900.py:50`: `pytestmark` still includes `pytest.mark.regression`. Remove it now that the tests are green (ADR 2026-07-17-1 / T018).

## 6. The fallback can overwrite a number the target already has (contradicts FR-007's "target wins")
`executor.py:~1510-1524`: when the bake returns None because the target ALREADY carries an assigned number for this mission (the no-op branch of `_compute_next_mission_number_or_none`), the executor still reads the mission branch's number and writes it onto the target tree. A stale mission-branch value would then silently replace the target's value, and verification passes because it checks the value just written.
Required: when the target's committed meta already has an assigned `mission_number`, use that as the expected value (or skip the write), and read the mission branch only when the target is unassigned. Add a test with target=3 and mission branch=5 that expects 3 after consolidation.

## Non-blocking observations
- `ordering.py:~813` `_assign_planning_only_mission_number_if_needed` still prints `✓ Assigned mission_number=N on target branch` before any read-back. Consider routing it through the same verify-then-announce step, via `run.assigned_mission_number`, so FR-006 holds on that path too.
- The consolidate tests call `_run_lane_based_consolidation` with a heavy mock set, including `_classify_porcelain_lines` returning ([], 0). As a result the porcelain-invariant whitelisting of `mission_number_meta_path` is never exercised, and git never invokes the merge driver (`spec-kitty` is not on PATH in the test env). Consider one test that leaves the porcelain classifier real.
