---
affected_files: []
cycle_number: 2
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T17:09:42Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP13
---

# WP13 review, cycle 2 (reviewer-renata): REJECT

Every cycle-1 item is fixed: B1, B2, B3, R1 and R2. The rework adds one new out-of-matrix red, the same class as B3. CI does not run that directory per PR.

## Blocking

### B4. `test_selector_resolution.py` create tests fail on `target_replacement`
- `tests/specify_cli/cli/commands/test_selector_resolution.py::test_agent_mission_create_canonical_succeeds`
- `tests/specify_cli/cli/commands/test_selector_resolution.py::test_agent_mission_create_alias_succeeds_with_warning`

Failure: `AttributeError("'types.SimpleNamespace' object has no attribute 'target_replacement'")`, exit code 1.

Cause: `_build_create_payload` and `_emit_create_result_phase` (`cli/commands/agent/mission_create.py`) now read `result.target_replacement`. The tests' `_fake_create_mission_core` returns a `SimpleNamespace` that lacks the field (lines ~401 and ~444).

Attribution: both tests pass on c02e879199 (the cycle-1 state, before f26efc0f26 and bf83480cce) and fail on bf83480cce.

Fix: add `target_replacement=None` to both fakes. Better, build them from a real `MissionCreationResult` so the next field cannot drift them. Then re-run `tests/specify_cli/cli/commands -k "create or specify or completion"` and record the result.

## Verified OK (cycle-1 items)
- B1: `tests/architectural/test_no_dead_symbols.py -p no:xdist`: 37 passed.
  - `coord_topology_reachable` is deleted with its tests.
  - `count_code_lanes` is in a new `category_c_topology_settlement_7282` with a WP14/#7282 exit.
  - `restamp_topic_branch_as_coordination` is in the widened section with the same exit.
  - The baselines moved 231->232 and 83->84, each with a justification.
  - `lane_cleanup.__all__` lost 9 names. All of them are still defined. `test_lane_cleanup_module.py` imports `LaneCleanupItem`, `LaneCleanupResult` and `PROCESS_IN_WORKTREE` directly, which still works. `landed_worktrees.py` has its own `PROCESS_PROOF_UNAVAILABLE`. No star imports and no `__all__` pins.
- B2: create's mint calls `switch_write_checkout` in `core/write_checkout_switch.py`. The refusal order is unchanged: applies, target has a commit, occupied, dirty (the create wording), branch exists, dirty backstop, switch. The old copies are gone. The façade-family frozen tuple drops three pre-split names and gives a reason, as its rule requires. The new leaf helpers are re-exported per the family rule (every leaf definition on the façade).
- B3: `_completion_manifest.json` is regenerated.
- R1:
  - `TargetReplacement` gives a human notice and a JSON `target_replacement`, which is null otherwise.
  - The `--target-branch` help is updated.
  - The orchestrator-api `specify` key pin is updated.
  - The docs row sits under "Response data (contract >= 1.24.0)", and the changelog bullet under `1.24.0`.
- R2: `make_coord_mission(topology: MissionTopology)`. The `None` tests are deleted.
- Goldens: the only changes are `target_replacement: null` and the dirty wording. `base_commit` is written only on regeneration and is never compared (`_mission_create_golden.assert_golden`, `_lane_base_commit` "never compared"), so it cannot flake.

## Non-blocking
- The core goldens' `base_commit` names f26efc0f26, the red commit, whose `src/` differs from the captured code. The field is informational only.
- The `lane_cleanup.__all__` trim edits a WP15-owned file. Watch for a conflict when lanes consolidate.

## Pre-existing reds in the same subset (also red on c02e879199, not WP13)
- `test_merge::test_mark_wp_merged_done_emits_done_when_lane_is_approved`
- `test_git_remedies::test_no_inline_destructive_git_advice_in_src` (`upgrade/tracked_meta_notice.py`)
- `test_merge_cli_golden` (`--dependency-ref`)
- `test_tasks_status_default_mission` x2
- `test_charter_generate_autotrack::test_status_json_error_is_parseable`
- `test_charter_ambiguous_directives` x2
- Charter-cascade, doctrine-asset and `test_activate_only_6408`, which are flaky under xdist and were not attributed to WP13.
