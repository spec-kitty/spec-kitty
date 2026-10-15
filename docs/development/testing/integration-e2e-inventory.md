---
title: Integration and e2e test inventory (2026-10-15)
description: The per-file audit of tests/integration and tests/e2e behind the test-pyramid rebalance plan, with each file's layer verdict and what an acceptance scenario would need.
doc_status: active
updated: '2026-10-15'
audience: docs/context/audience/internal/lead-developer.md
type: reference
related:
- docs/development/testing/test-pyramid-rebalance.md
- docs/adr/4.x/2026-10-15-1-qa-and-core-share-the-acceptance-scenarios-and-absorb-engineering-tests-through-a-ledger.md
---

# Integration and e2e test inventory (2026-10-15)

A dated snapshot of the 184 test files under `tests/integration` (177) and `tests/e2e` (7) at commit `f87ecb8a21`, made for the [test-pyramid rebalance plan](test-pyramid-rebalance.md). The same file list is frozen as the `baseline` of `tests/scenarios/absorption-ledger.json`, which is the checked record. This page is the reasoning behind it and is not updated as files move; the ledger is.

**Verdicts** (the decision rules are in the plan):

| Verdict | Meaning |
|---|---|
| scenario | The whole file can be checked black-box through the built CLI. |
| partly | Some tests can move; the others need internals. |
| keep | Needs internals (patches, injected faults, hand-made internal state, in-process APIs). Stays pytest. |
| unit | Integrates nothing; belongs in the module's unit tree. |
| duplicate | Covered by the test named in the reason. "Unverified" means the overlap still needs a reviewer. |
| p0 | A P0 reproduction (nightly `p0-repro` lane). |

**Wave** is the plan's wave that moves it, with "(done)" once it has, or "(decided)" where the wave decided the file stays pytest: 1, 1b, 1c, 2 (authored-content Arrange, ADR 2026-10-15-1 decision 6), 3 (needs an org-pack CLI command, #6267), D (moved to the unit tier), R (duplicate review). Verdicts are as audited on 2026-10-15, corrected where checking a file changed its verdict.

## tests/e2e

| File | Verdict | Wave | Reason |
|---|---|---|---|
| `test_charter_epic_golden_path.py` | keep | 2 (decided) | One chained run whose distinctive checks read the internal lifecycle log and guard the source tree against pollution, which means nothing against a wheel; its charter, planning and status steps are covered by `charter/charter.feature` and `mission/lifecycle.feature`. It is the only test of `charter bundle validate`. |
| `test_cli_smoke.py` | partly | 1, 2 (done) | Create, documentation create, the refusals, `setup-plan` and the full flow to review moved to `mission/mission-create.feature` and `mission/lifecycle.feature`. The template-override test writes `.kittify/overrides/` (CLI-managed) and stays. |
| `test_coord_status_off_target_lifecycle.py` | scenario | 2 (done) | Moved to `mission/lifecycle.feature`: status stays off the target branch and on the coordination branch. |
| `test_feature_alias_smoke.py` | scenario | 1 (done) | The retired Mission alias option is refused with exit 2 ([migration note](../../migrations/feature-flag-deprecation.md)). Retired into `mission-create.feature`. |
| `test_mission_create_clean_output.py` | unit | D (done) | A source scan and three in-process checks of the diagnostics module; moved to `tests/specify_cli/cli/commands/agent/`, and the one test that could not fail was deleted. |
| `test_upgrade_post_state.py` | keep | - | Writes a legacy `.kittify/metadata.yaml`; a scenario would need an older wheel. |
| `test_worktree_owned_root_concurrency.py` | keep | 2 (decided) | Concurrency with a barrier and measured overlap, and the retry helper's unit tests; scenarios run one CLI command at a time. |

## tests/integration (top level)

| File | Verdict | Wave | Reason |
|---|---|---|---|
| `test_2646_stale_verdict_closes_via_fr001.py` | keep | - | In-process rejected-review cycle, 11 patches. |
| `test_2939_move_task_clean_tree_after_rejection.py` | keep | - | `_do_move_task` with a fault-injecting router. |
| `test_ac5_hash_guard.py` | keep | - | Patched lifecycle; byte-hash of WP files. |
| `test_accept_matrix_coord_partition.py` | keep | - | Commit-router partition seams with spies. |
| `test_agent_identity_prompt.py` | unit | D (done) | Pure prompt rendering. |
| `test_analysis_template_mirrors.py` | keep | - | Patched resolver home, injected write race. |
| `test_branch_strategy_gate.py` | unit | D (done) | Pure `evaluate_branch_strategy`. |
| `test_catalog_miss_cli_visibility.py` | scenario | 3 (blocked on #6267) | Unknown styleguide warns in `charter context`; registering the org pack today means writing `.kittify/config.yaml`. |
| `test_charter_lint_lints_all_layers.py` | scenario | 3 (blocked on #6267) | Lint names every layer; registering the org pack today means writing `.kittify/config.yaml`. |
| `test_charter_status_freshness.py` | partly | 1c (done) | The freshness shape and synthesis-missing cases moved to `charter/charter.feature`; the all-fresh, invalid and legacy-bundle states need crafted bundle files and stay. |
| `test_charter_status_reports_three_layers.py` | scenario | 3 (blocked on #6267) | Same org-pack arrange as lint. |
| `test_charter_synthesize_built_in_only.py` | unit | D (done) | Post-condition helper on temporary files. |
| `test_charter_synthesize_fresh.py` | partly | 1c (done) | The fresh seed, dry run, re-run and missing-charter cases moved to `charter/charter.feature`; the stale-graph unlink and registered-artifact cases need crafted files under `.kittify/` and stay. |
| `test_clean_install_next.py` | keep | - | Builds its own wheel and checks that importing the CLI loads no retired runtime package; `next --json` from a wheel is now also in `init.feature`. |
| `test_cli_status_mediation.py` | keep | - | In-process read-path resolution. |
| `test_colliding_mission_flow.py` | keep | - | Legacy number collisions the CLI cannot create. |
| `test_consolidate_upgraded_mission_recovery.py` | keep | - | Forges older-version upgrade state. |
| `test_coord_loop_depgraph.py` | keep | - | Routing proofs on a crafted coordination husk. |
| `test_coord_loop_tasks.py` | keep | - | Same seam, tasks call sites. |
| `test_coord_loop_workflow.py` | keep | - | Same seam, workflow call sites. |
| `test_coord_loop_workspace.py` | keep | - | Same seam, workspace call sites. |
| `test_coord_read_residuals_proof.py` | keep | - | Sentinel-husk divergence, 21 patches. |
| `test_coord_single_home_workflow.py` | keep | 2b (decided) | Its decisive check is that no coordination-only path reached the target before consolidation, which needs the coordination/primary file split; the flow itself is covered by `mission/lifecycle.feature` and `consolidate/consolidate.feature`. |
| `test_coord_topology_smoke.py` | keep | - | Self-test of a shared fixture. |
| `test_coord_unprotected_lifecycle_loop.py` | keep | - | Imports allocator internals, writes `meta.json`. |
| `test_custom_mission_runtime_walk.py` | keep | - | Patched step executor. |
| `test_deferral_enforcement_and_disclosure.py` | unit | D (done) | CI checker over temporary JSON. |
| `test_documentation_runtime_walk.py` | keep | - | In-process run composition. |
| `test_dossier_snapshot_no_self_block.py` | keep | - | Path filters and a patched readiness check. |
| `test_explicit_checkout_commands.py` | keep | - | Symlink escapes, broken pointers, 28 patches. |
| `test_fail_loud_uninitialized_repo.py` | unit | D (done) | Calls the `assert_initialized` helper directly; at the CLI, `specify` resolves to the git root, so these are helper rules, not CLI promises. The CLI refusal outside a project is now a scenario (new coverage). |
| `test_handoff_lane_read_coord.py` | keep | - | Crafted husk, executed-revert patch. |
| `test_identity_coord_read.py` | keep | - | Identity routing on a sentinel husk. |
| `test_implement_review_flow.py` | keep | - | Forced commit failure, rollback, concurrency. |
| `test_implement_review_retrospect_smoke.py` | keep | - | Patched synthesizer, seeded events. |
| `test_init_fresh_project_chain.py` | partly | 1b (done) | A fresh `init` is ready for `next` moved to `init.feature`; the private stamp helper test stays. |
| `test_intake_atomic_writes.py` | keep | - | Fork and SIGKILL fault injection. |
| `test_intake_size_cap.py` | unit | D (done) | `read_brief` on temporary files. |
| `test_internal_runtime_engine.py` | unit | D (done) | In-process engine on YAML fixtures. |
| `test_is_committed_contract.py` | keep | - | Caller contract with a patched pin. |
| `test_issue_2404_acceptance_matrix_write_surface.py` | keep | - | Static call-site census. |
| `test_issue_3716_discard_transactional_close_guard.py` | partly | 1b (done) | The clean-tree and abandoned-provenance cases moved to `mission/mission-close.feature`; the failure cases patch bookkeeping and stay. |
| `test_issue_3784_coord_tasks_md_primary_bundle_guard.py` | keep | - | Inspects the `safe_commit` bundle. |
| `test_issue_4765_close_guard.py` | keep | - | Hand-made unmerged, in-flight coordination Mission with a live worktree; a CLI-made Mission is a different arrange. |
| `test_issue_4863_merge_abort_no_state.py` | partly | 1b (done) | The no-state abort moved to `consolidate/abort.feature`; the real-abort test fakes merge state and stays. |
| `test_issue_verdict_concurrent_lock.py` | keep | - | Lost-update race, lock timeout. |
| `test_issue_verdict_coord_legacy_md_preservation.py` | keep | - | Hand-built legacy matrix. |
| `test_issue_verdict_selfmat_hardening.py` | keep | - | Hand-built stale coordination branch. |
| `test_lane_db_isolation.py` | unit | D (done) | Pure naming functions. |
| `test_lane_lifecycle_sync.py` | keep | - | Hand-written lane manifest. |
| `test_lanes_core_coord_read.py` | keep | - | Capture patches on read paths. |
| `test_legacy_feature_alias.py` | duplicate | 1 (done) | Subsumed by `test_terminology_guards.py`; retired. |
| `test_legacy_mission_fallback.py` | keep | - | Forced commit failure and rollback. |
| `test_merge_abort_scope.py` | partly | 1 (done) | The #4754 case moved to `consolidate/abort.feature`; the parity cases fake merge state. |
| `test_merge_cluster_coord_read.py` | keep | - | Primary-vs-husk routing, hand-made `meta.json`. |
| `test_merge_gates_coord_per_leg.py` | keep | - | `evaluate_merge_gates` in-process. |
| `test_merge_lane_planning_data_loss.py` | keep | - | Mocked merge plan, 61 patches. |
| `test_merge_lane_worktree_safety.py` | keep | - | Mocked harness, private preflight. |
| `test_merge_primary_checkout_safety.py` | keep | - | Mocked harness; its promise needs a mergeable-Mission builder (wave 2). |
| `test_merge_resume.py` | keep | - | Mocked lane consolidations, 19 patches. |
| `test_migration_backfill.py` | keep | - | Fault-injected corrupt seed. |
| `test_mission_archiving.py` | keep | 1c (decided) | Pins the archive API's refusal codes (AM-1, AM-2) on hand-made terminal states; a CLI scenario would be extra coverage, not a replacement. |
| `test_mission_close.py` | duplicate | R (done) | Verified: its two product tests are covered by `tests/specify_cli/coordination/test_workspace.py` (one HEAD check folded in); its other five ran only plain git or tested the test's own branch. |
| `test_mission_close_discard_coord_teardown.py` | keep | - | Hand-made split-brain `meta.json` and lanes. |
| `test_mission_close_discard_single_branch.py` | partly | 2 (done) | The discard from the minted branch and the dirty-checkout refusal moved to `mission/mission-close.feature`; the no-meta case writes a crafted residue file and stays. |
| `test_mission_review_contract_gate.py` | keep | - | Writes status events, calls `review_mission`. |
| `test_mission_run_command.py` | keep | 1c (decided) | The broken custom Mission definitions live under `.kittify/missions/`, CLI-managed state a scenario builder may not write (ADR 2026-10-15-1, decision 6); the happy path stubs the run. |
| `test_mission_type_profile_live_wiring.py` | keep | - | Private prompt builder, hand-made `meta.json`. |
| `test_mission_type_resolution_integration.py` | keep | - | Resolver against hand-made `meta.json`. |
| `test_monorepo_charter_scope.py` | unit | D (done) | `CharterScope.resolve` over a temporary tree. |
| `test_next_lifecycle_records.py` | keep | - | Fake `decide_next`. |
| `test_next_preview_primary_routing.py` | keep | - | Private decision builder. |
| `test_org_pack_artifact_lifecycle.py` | keep | - | In-process charter context. |
| `test_org_pack_chain_delivery.py` | keep | - | DRG merge invariants. |
| `test_org_pack_missing_path_hard_fails.py` | keep | - | Calls `load_org_drg` directly. |
| `test_org_pack_subdir_e2e.py` | keep | - | Private collectors, mocked fetch. |
| `test_owned_analysis_recording.py` | keep | - | Races, symlinks, patched resolver home. |
| `test_owned_charter_generation.py` | keep | - | Claim-counting spies. |
| `test_owned_checkout_mark_status.py` | keep | - | Rollback, concurrent events, counters. |
| `test_owned_decision_runtime_lock.py` | keep | - | Hand-written locks, hook rejections. |
| `test_owned_fixtures_selftest.py` | keep | - | Fixture self-tests. |
| `test_owned_lifecycle_acceptance_cli.py` | keep | 2b (decided) | The refusal matrix runs five commands over six paths with snapshots of the repository, the owned checkout and the home directory; in-process that is seconds, as black-box scenarios about thirty per OS, and the home snapshot has no black-box equivalent. |
| `test_owned_lifecycle_acceptance_context.py` | keep | - | Hand-made stale copies and pointers. |
| `test_owned_lifecycle_acceptance_documentation.py` | keep | - | Stale-copy fixture. |
| `test_owned_lifecycle_acceptance_e2e.py` | keep | 2b (decided) | The walk counts validations and subprocesses and uses a provisioned test charter; the quickstart part restates flows `mission/lifecycle.feature` checks. |
| `test_owned_lifecycle_acceptance_finalize.py` | keep | - | Commit-failure injection, cyclic lanes. |
| `test_owned_lifecycle_acceptance_next.py` | keep | - | 81 patches, injected failures. |
| `test_owned_lifecycle_acceptance_review.py` | keep | - | Private gate flag, 57 patches. |
| `test_owned_lifecycle_acceptance_status.py` | keep | - | 111 patches. |
| `test_owned_map_requirements.py` | keep | - | Spies on the owned-task resolver. |
| `test_owned_next_runtime.py` | keep | - | In-process runtime, injected git failures. |
| `test_owned_pr_bound_finalization.py` | keep | - | Patched legacy finalize helpers. |
| `test_owned_protected_single_branch.py` | keep | - | In-process minter chain. |
| `test_owned_research_placement.py` | keep | 2b (decided) | The arrange writes `.kittify/config.yaml` and research templates, CLI-managed state a builder may not write. |
| `test_p0_pinning_regressions.py` | keep | - | Internal errors and a flattened `meta.json`. |
| `test_p0_repro_5932_consolidate_canceled_dependency.py` | p0 | - | CLI-only; a scenario with `@defect:5932` once fixed. |
| `test_p0_repro_5939_single_branch_autowalk.py` | p0 | - | CLI-only; a scenario with `@defect:5939` once fixed. |
| `test_pack_enhances_partial_fields.py` | unit | D (done) | Repository merge semantics on temporary YAML. |
| `test_pack_skill_lifecycle.py` | keep | - | In-process skill installer. |
| `test_placement_partition_golden_path.py` | keep | - | Partition invariants, 23 patches. |
| `test_planning_artifact_wp.py` | unit | D (done) | Enum and resolver checks. |
| `test_post_merge_custom_mission_loader.py` | unit | D (done) | In-memory registry. |
| `test_post_merge_index_refresh.py` | keep | - | Patched subprocess. |
| `test_post_merge_unrelated_untracked.py` | partly | 2 (done) | The untracked-files consolidate moved to `consolidate/consolidate.feature`; the porcelain classifier tests are unit-level and the tracked-change case patches the porcelain read, so they stay. |
| `test_pre30_layout_coord_husk_noop.py` | keep | - | Crafted husk. |
| `test_prompt_builder_owned_arms.py` | keep | - | `build_prompt` with seeded events. |
| `test_protected_primary_spec_commit.py` | keep | - | Stubbed `commit_for_mission`. |
| `test_quickstart_end_to_end.py` | partly | 1c (done) | Steps 1, 3 and 5 moved to `charter/charter.feature`; step 2 stubs freshness and step 4 calls the pack validator API, so they stay. |
| `test_refinalize_frozen_lane_refusals.py` | keep | 2b (decided) | Every row needs two started lanes and several finalize runs; its spy and malformed-log rows need internals, and its black-box rows restate the refusal the kept spy test pins and the lane rule `mission/refinalize.feature` checks. |
| `test_refinalize_keeps_started_lanes.py` | partly | 2 (done) | The two started-lane cases moved to `mission/refinalize.feature`; the claimed-only case needs an allocated worktree with a claimed status, which the CLI never leaves, and the refusal pair uses writer spies, so they stay. |
| `test_rejection_cycle.py` | keep | - | Helper checks on a hand-made manifest. |
| `test_render_parity_golden.py` | unit | D (done) | Render compared with a golden file. |
| `test_research_runtime_walk.py` | keep | - | Runtime engine internals. |
| `test_review_cycle_rejection_only.py` | partly | 2 (done) | The counter and two-rejection cases moved to `mission/review.feature`; the approval-artifact case stays. |
| `test_review_durability_matrix.py` | keep | - | Removes governed-ref commits, patches seams. |
| `test_review_handoff.py` | keep | - | Private readiness check. |
| `test_sc008_topology_resolution.py` | keep | - | Emit destinations, 9 patches. |
| `test_single_branch_lane_preview.py` | keep | - | Preview vs finalize parity through `compute`. |
| `test_single_branch_write_checkout_e2e.py` | partly | 2 (done) | The review commit gate, the claim commit, stray files, and the occupied and dirty checkout moved to `mission/single-branch.feature`; the lanes control, claim-base, resume and cross-mission cases read internal records and stay. |
| `test_slice_f_cross_axis.py` | keep | - | In-process DRG composition. |
| `test_specify_plan_commit_boundary.py` | partly | 2 (done) | The create and setup-plan gate cases moved to `mission/plan.feature`; the `is_substantive`/`is_committed` checks are unit-level and the template-override cases need `SPEC_KITTY_HOME`/template-root overrides, so they stay. |
| `test_status_emit_on_alloc_failure.py` | keep | 2b (decided) | The dependency-lane conflict is seeded with canonical status state, and the other cases inject the failure. |
| `test_surface_translation_seam.py` | keep | - | Surface-translation invariants. |
| `test_target_owned_fixtures_selftest.py` | keep | - | Fixture self-test. |
| `test_three_layer_drg_end_to_end.py` | unit | D (done) | Loader and merge on temporary files; never runs the CLI. |
| `test_tool_artifact_owner.py` | keep | - | Compensator and a SIGKILL barrier. |
| `test_two_partition_preview.py` | keep | - | Seeded events, preview vs consolidation. |
| `test_upgrade_live_lanes_cli.py` | keep | - | Crafts older-version state. |
| `test_user_doctrine_artifact_lifecycle.py` | keep | 2b (decided) | Builds the charter context in-process; the implement prompt's location is internal, so a black-box check would read an internal file. |
| `test_workflow_sequence_runtime.py` | unit | D (done) | Planner output from a hand-made `meta.json`. |
| `test_worktree_topology_claim_base.py` | keep | - | Seeded coordination events. |
| `test_wp_file_hash_stability.py` | keep | - | Patched subprocess and sleep. |
| `test_wp_integrity_checkout_identity.py` | keep | - | Workspace chokepoint and an `inspect` table. |
| `test_wp_integrity_crash_recovery.py` | keep | - | Simulated crash. |
| `test_wp_integrity_cross_partition_scan.py` | keep | - | Internal coherence classifiers. |
| `test_wp_integrity_p0_repro.py` | keep | - | Private planning-commit helper. |

## tests/integration subfolders

| File | Verdict | Wave | Reason |
|---|---|---|---|
| `git/test_safe_commit_backstop.py` | keep | - | Plants a phantom deletion through a patched subprocess. |
| `migration/test_audit_primary_anchor.py` | keep | - | Spies on `run_audit`. |
| `migration/test_audit_trail_durability_4928.py` | keep | - | Hand-written legacy rows. |
| `migration/test_canonicalization_pipeline.py` | unit | D (done) | Private canonicalization functions. |
| `migration/test_lifecycle_events_preserved.py` | keep | - | Private `_repair_mission`. |
| `migration/test_mission_state_repair_fidelity_e2e.py` | keep | - | Hand-made `meta.json` and a corrupt log. |
| `migration/test_noop_upgrade_leaves_history_untouched.py` | keep | 2b (decided) | Its value is crafted out-of-order and identity-less legacy history, which the CLI cannot produce; on CLI-made history the no-op is trivially true. |
| `migration/test_repair_normalizes_change_mode.py` | keep | - | Legacy `change_mode` in `meta.json`. |
| `migration/test_repair_primary_anchor.py` | keep | - | Crafted drift state. |
| `migration/test_residue_dir_not_treated_as_mission.py` | keep | - | The arrange is a crash leftover written under `kitty-specs/`, which a scenario builder may not write (ADR 2026-10-13-1, decision 5). |
| `migration/test_wp03_advance_to_approval.py` | keep | - | Seeded wedged log, private flag. |
| `retrospective/test_autonomous_terminus_e2e.py` | keep | - | `run_terminus` with a synthetic facilitator. |
| `retrospective/test_default_flow_generator_failure.py` | keep | - | Patched generator. |
| `retrospective/test_default_flow_healthy.py` | keep | - | Private callback builder. |
| `retrospective/test_hic_terminus_e2e.py` | duplicate | 1 (done) | Folded into `test_lifecycle_hook.py`; retired. |
| `retrospective/test_lifecycle_hook.py` | keep | - | The `run_terminus` matrix. |
| `retrospective/test_next_mission_sees_change.py` | keep | - | In-process terminus and proposals. |
| `retrospective/test_opt_out.py` | keep | - | Private callback builder. |
| `retrospective/test_policy_source_attribution.py` | duplicate | R (done) | Verified: its two unique checks were folded into the default-flow tests, then it was retired. |
| `retrospective/test_silent_auto_run_blocked.py` | keep | - | Gate API with seeded events. |
| `retrospective/test_silent_skip_blocked.py` | keep | - | Gate API with seeded events. |
| `retrospective/test_strict_flow_block.py` | keep | - | Strict policy, patched generator. |
| `retrospective/test_strict_flow_skip.py` | keep | - | `emit_skipped` ordering. |
| `retrospective/test_strict_flow_skip_empty_reason_rejected.py` | unit | D (done) | One `ValueError` check. |
| `retrospective/test_wp04_coverage_branches.py` | unit | D (done) | Private classification helpers. |
| `review/test_approve_without_force.py` | keep | 2 (decided) | Drives the readiness check and pins the deny-list and lock cleanup directly, for approval and rejection; approving after review without `--force` is exercised through the CLI by every scenario that reaches `approved`. |
| `review/test_canonical_review_diff_refs.py` | keep | - | Private review context. |
| `review/test_reject_from_in_review.py` | partly | 2 (done) | The rejection, the empty-feedback refusal and the declared reviewer moved to `mission/review.feature`; the stale review-override case needs crafted events and stays. |
| `review/test_reject_without_force.py` | duplicate | R (done) | Verified: folded into `test_approve_without_force.py` as a parametrize over approved and planned, plus its default-lane case. |
| `review/test_verdict_save_topologies.py` | keep | - | Multiprocessing, 19 patches, fault injection. |
| `sparse_checkout/test_detection.py` | keep | - | Git config storage and lane registration internals. |
| `sparse_checkout/test_doctor_finding.py` | partly | 1 (done) | Three detection cases moved to `doctor/sparse-checkout.feature`; managed-lane cases need `register_lane_sparse_checkout`. |
| `sparse_checkout/test_doctor_non_interactive.py` | partly | 1 (done) | The non-terminal case moved; probe rules and interactive answers stay. |
| `sparse_checkout/test_implement_preflight_blocks.py` | scenario | 1b (done) | Moved to `implement/sparse-checkout.feature`; its `--force` case is now meaningful (`--force --note`). |
| `sparse_checkout/test_merge_preflight_blocks.py` | scenario | 1b (done) | Moved to `consolidate/sparse-checkout.feature`; `consolidate` has no `--force`, which the scenario pins. |
| `sparse_checkout/test_merge_refresh_and_invariant.py` | keep | - | Ordering of patched collaborators. |
| `sparse_checkout/test_merge_with_allow_override.py` | keep | - | Patched preflight, caplog. |
| `sparse_checkout/test_remediation_primary.py` | keep | - | Not a duplicate: it pins the primary-only remediation steps and config removal. |
| `sparse_checkout/test_remediation_primary_and_worktrees.py` | keep | - | Calls `remediate()`; the CLI path needs a terminal. |
| `sparse_checkout/test_remediation_refuses_on_dirty.py` | keep | - | Dirty refusal through `remediate()`. |
| `sparse_checkout/test_session_warning_once.py` | duplicate | R (done) | Verified: its first-label check was folded into the unit tests, then it was retired. |
