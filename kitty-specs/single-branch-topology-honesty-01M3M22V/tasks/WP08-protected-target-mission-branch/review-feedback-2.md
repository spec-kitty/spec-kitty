# WP08 review feedback, cycle 2 (reviewer-renata)

**Verdict: changes requested.** All four cycle-1 items are fixed, and every mutation I repeated is caught (see "Verified"). However, the new consolidate gating regresses legacy and planning-only missions.

## Blocking

**Issue 1: `lands_mission_branch` misclassifies planning-only and legacy missions. There are 5 new failures in `tests/integration/test_merge_lane_planning_data_loss.py`.**

- **Evidence.** I ran the same file serially, isolated, on f6921c10 (cycle-1 head) and on 40ed5003 (HEAD):

  | Commit | Result |
  |---|---|
  | f6921c10 | 12 passed, 5 failed (the known #5044 set: `TestMergeIncludesPlanningLane` plus the 4 `TestRetentionConstraintSurvivesCleanup` tests) |
  | 40ed5003 | 7 passed, 10 failed: the same 5 **plus 5 new failures** |

  The 5 new failures:
  - `TestLegacyPlanningOnlyMetaInvariant::test_legacy_planning_only_meta_json_does_not_trip_invariant`
  - `TestLegacyPlanningOnlyMetaInvariant::test_meta_json_membership_is_load_bearing`
  - `TestPlanningOnlyDoneMarkingPersists::test_planning_only_done_events_are_persisted_and_readable`
  - `TestPlanningArtifactReachesTarget::test_planning_artifact_only_merge_does_not_require_mission_branch`
  - `TestPlanningArtifactReachesTarget::test_planning_only_bookkeeping_reaches_target_branch`

  Representative error: `Error: Missing mission branch: kitty/mission-real-merge-planning-only-research. Run: git branch kitty/mission-real-merge-planning-only-research …`.

- **Root cause.** `single_branch_landing._is_protected_single_branch` decides "protected single_branch landing" from two inputs:
  - `manifest.mission_branch != manifest.target_branch`: every non-single_branch and legacy `lanes.json` carries `mission_branch = kitty/mission-<slug>`, so this is true for all of them;
  - `resolve_topology(...)`, which **derives** `single_branch` for a mission with no stored `topology` and no code lanes. That covers every legacy planning-only mission.

  So a plain planning-only legacy mission now reads as `lands_mission_branch`. Four consequences follow:
  - `planning_artifact_only` flips to False;
  - `done_marked_before_target` flips;
  - the mission→target landing demands a branch that never existed;
  - coord teardown is skipped.

  The cycle-2 fixes (`planning_artifact_only`, the preflight, `done_marked_before_target`, coord teardown) are therefore **not** scoped to protected single_branch landing.

- **Required fix.**
  - Key `lands_mission_branch` / `_is_protected_single_branch` on the **mint marker**:
    - the **stored** topology is `single_branch`, via `backfill_topology.stored_topology`, never the derived one;
    - AND `meta.json` records a `mission_branch`, which is written only by the protected-target mint;
    - AND that value differs from `target_branch`.
  - Do not use the lanes manifest's `mission_branch` or `resolve_topology` for this decision. `authorship_window` shares the helper, so the same fix covers it.
  - Add a unit control: a legacy planning-only mission (no stored topology, manifest `mission_branch = kitty/mission-…`) gives `lands_mission_branch is False`.
  - Re-run `test_merge_lane_planning_data_loss.py`. It must return to the base's 5 known failures (#5044).

## Verified (cycle-1 items resolved)

- **Item 1 (status transition).** `test_status_transition_commits_to_mission_branch_not_target` drives `implement` through the committing router and asserts a new tip on `mission_branch`. W1 is now caught by 5 tests: the e2e consolidate tests, the status test, wrong-branch, and the #5100 protected test.
- **Item 2 (resolver).** HEAD `resolver.py` passes `target_branch=authoritative_target`. The mutated commit f4b581dd was fixed in 40ed5003. W2 is caught by `test_authoritative_ref_is_mission_branch_for_protected_mission`.
- **Item 3 (recovery/doctor).** `test_minted_mission_branch_not_classified_by_recovery_or_doctor` has a non-vacuous glob precondition and covers recovery, the doctor topology finding and the coordination findings.
- **Item 4 (end to end).** `test_single_branch_consolidate_e2e.py` drives `_run_lane_based_consolidation`, the executor entry that `spec-kitty consolidate` calls. The tautological retention test is gone.
  - Switch-back mutation: 3 tests fail.
  - `sb_window` mutation: 4 tests fail, including both e2e tests.
- **Cleanliness.** The lane-h working tree is clean. `git diff --stat f6921c10..HEAD` shows no unrelated reformatting. `executor.py` is +21/−9, with the logic in `lanes/single_branch_landing.py`.
- **Tests.**
  - The WP08 list: 66 passed. It covers the create/mint file, the e2e file, `mission_to_target`, the #5100 integration file, `protection_policy_protected_target` and `context/test_resolver`; the recovery test lives in the create/mint file.
  - Gates: `test_no_dead_symbols` 34, `test_layer_rules` 74.
  - ruff is clean.
- **Scope note.** `test_issue_2745_merge_skip_lanes.py` (4 tests) and `test_merge_strategy.py` / `test_specify_topology_flag` e2e: the skip-lanes file is red at f6921c10 but green at HEAD. The others are red on both commits, so they are not attributable to this cycle.
