# WP04 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The design is right. Four blocking items:

- two behaviour regressions, both reproduced green on base 3ca95083 and red on HEAD daf345d8;
- one refusal no test pins (a surviving mutant);
- required tests that are missing.

## Blocking

**Issue 1: the write-checkout refusals fire for every repo-root lane, not only for single_branch missions. This is a regression for planning_artifact WPs in lanes and coord missions.**

- **Where.** `lanes/implement_support.py::create_lane_workspace` calls `_ensure_repo_root_checkout_available` whenever `is_repo_root_lane(resolved_workspace)`. Every planning_artifact WP of every topology resolves to `lane-planning`, so it passes that check too.
- **Contract.** `contracts/single-branch-execution.md` scopes "Implement: refusals" to single_branch, and the WP prompt says "for a WP in a repo-root lane **of a single_branch mission**".
- **Reproduction.** A lanes-topology mission with one `execution_mode: planning_artifact` WP, and an untracked `operator_scratch.txt` in the repo root:

  | Commit | Result of `implement WP01` |
  |---|---|
  | base 3ca95083 | exit 0 |
  | HEAD | exit 1, `WRITE_CHECKOUT_DIRTY: ... uncommitted changes: operator_scratch.txt` |

  A dirty repo-root checkout is the normal state while planning, so this breaks planning-WP implement across every non-single_branch mission.
- **Required fix.**
  - Gate the refusal block on the stored topology being single_branch (`read_topology` / `topology_from_meta`). Keep claim-base recording lane-keyed as it is today.
  - Add a lanes-topology planning_artifact control test through the CLI: a dirty checkout and a non-target HEAD are both still allowed.

**Issue 2: regression in `tests/integration/test_merge_lane_planning_data_loss.py::TestPlanningArtifactReachesTarget::test_planning_only_bookkeeping_reaches_target_branch`. It is green on base and red on HEAD.**

- **Symptom.** `Error: Post-merge target validation failed: merged WPs did not reach done in target branch history.`
- **Cause.**
  - `consolidation/executor.py::_run_has_code_wps` builds kinds from `entry.metadata.execution_mode or WorkProductKind.CODE_CHANGE`. A WP file without an explicit `execution_mode`, which is legal for legacy missions and is the shape this fixture uses, therefore counts as CODE.
  - A planning-only mission then stops skipping `_run_birth_cutover`, which was previously gated on `planning_artifact_only`, and the merge fails.
- **Required fix.**
  - Derive the kind the same way the resolver does: the normalized, inferred mode (`mode_source`), not a raw-frontmatter default.
  - Or keep the lane-based `planning_artifact_only` short-circuit as a floor, so `has_code_wps` can only *add* code, never reclassify a lane-planning-only mission.
  - Keep this test green, and add a unit test for `_run_has_code_wps` with a WP that has no `execution_mode` in a planning-only manifest.
  - Re-check `gates_core.py:277,770` for the same default-to-CODE hazard.

**Issue 3: the `WRITE_CHECKOUT_WRONG_BRANCH` refusal is untested.**

- **Evidence.** Mutation M5 replaced `if expected_branch is not None and current_branch != expected_branch:` with `if False:`. All 41 tests across the six new files still passed.
- **Why.** `test_wrong_branch_refuses` also passes at the red commit 9383ee62: something pre-existing refuses first, and the test only asserts `exit_code != 0` plus the two branch names in the output.
- **Required fix.**
  - Assert the stable error code `WRITE_CHECKOUT_WRONG_BRANCH` and the remedy line (NFR-004).
  - Likewise assert `WRITE_CHECKOUT_OCCUPIED` / `WRITE_CHECKOUT_DIRTY` and their remedies in the occupied and dirty tests; today none of the refusal tests asserts an error code.
  - Confirm the wrong-branch test fails when the check is removed.

**Issue 4: required tests are missing.** A grep of the whole WP04 test diff for readiness, `--merges`, `stale_detection` and `skip_lanes` finds none of these:

- **T019, dependency readiness (post-tasks fold M-1).** WP01 is in `for_review` and WP02 depends on it. `implement WP02` must be refused on dependency **readiness**, and the error must not be `WRITE_CHECKOUT_OCCUPIED`.
- **T019, no dependency merge.** Implementing a repo-root-lane WP creates no merge commit (`git log --merges` is empty). This also pins the `worktree_allocator.py` skip hunk.
- **T019, status view.** `tasks_status_view.py:140` does not report a repo-root code WP as `stale_detection_unavailable`. The src hunk has no test.
- **T020, `--skip-lanes` control.** The prompt requires that `--skip-lanes` (`_synthesize_no_lane_manifest`) stays green. There is no test in `test_single_branch_bookkeeping_only.py`.

## Non-blocking

**Nit 5: red-first.**
- At 9383ee62 most behaviour tests are assertion-red. The import-level red is limited to the brand-new module (`checkout_occupancy`), the new `effective_root` kwarg (TypeError) and one new property, which is acceptable.
- However, 14 tests pass at red. Most are legitimate controls (the lanes/worktree params, the protected-target control, the real-mission-branch delete control).
- These five do not discriminate the new code: `test_review_of_repo_root_wp_creates_no_worktree`, `test_phase_mission_to_target_is_a_noop_for_bookkeeping_only`, `test_phase_merge_lanes_skips_the_repo_root_lane`, `test_fresh_claim_succeeds_with_no_worktree_and_direct_repo_stamp`, and the resume test. Either make them discriminating or label them as characterization in their docstrings.

**Nit 6: orchestrator `transition()`.** It now calls `_resolve_existing_workspace` for every non-claimed and non-for_review target (`done`, `canceled`, `blocked`, and so on) just to pick a stamp. Confirm this cannot raise for a legacy or no-lanes mission on a terminal transition; if it can, apply the same tolerant fallback move-task uses.

**Nit 7: repo-root-lane arm scope.** `_resolve_repo_root_lane_arm` is keyed on the lane only and sets `branch_name = mission_branch or target_branch`. For a lanes or coord mission, `mission_branch` is `kitty/mission-…`. That is harmless today, because planning_artifact WPs are caught earlier by the planning_artifact arm. Once Issue 1 is fixed, consider keying the arm on single_branch too, to match the contract's resolve table.

## Verified OK

**Mutations.** Four were caught, in addition to the M5 survivor above:

| Mutation | Test that failed |
|---|---|
| M1: resolver precedence swapped | `test_stale_workspace_context_does_not_shadow_repo_root_lane` |
| M2: occupancy check disabled | `test_another_mission_in_progress_refuses` |
| M3: resume exemption removed | the resume test |
| M4: move-task stamp hardcoded to `"worktree"` | `test_move_task_stamps_execution_mode[single_branch-direct_repo]` |

**Other checks.**
- `effective_root` is keyed on the stored topology and raises for non-single_branch (tested).
- Commit 6feed894 carries the `Co-authored-by: samuelgoff` trailer and cites PR #5009.
- `read_topology` now delegates to `topology_from_meta`, with the same behaviour.
- `_delete_mission_branch` returns early when `mission_branch == target_branch` (tested), so it cannot delete the target branch.
- The orchestrator merge at `:997` already routes a single-lane manifest through `is_planning_artifact_only` → `_execute_planning_only_merge`.
- The gates pass: `test_layer_rules` 74, `test_no_dead_symbols` 34, `test_mission_runtime_surface` 7.
- `ruff check` is clean. The 7 files that would be reformatted were all already unformatted on base. The mypy error set in `executor.py` / `gates_core.py` is identical to base.

**Pre-existing reds, confirmed.** None is a WP04 regression:
- `test_canonical_acceptance.py`: 13, red on base too.
- `test_merge_lane_planning_data_loss`: 5, red on base too (#5044).
- `test_birth_cutover`: #4787.
- `test_verdict_provenance_backfill`: #5279.
- `test_dogfood_corpus_backfilled`: #5300.
- The 14 charter CLI tests fail in any linked worktree, including a base-source one, and pass on the root checkout.
