---
title: 'Post-Mission Test Baseline: 01KSMG8Y'
description: 'Post-mission test baseline for the 01KSMG8Y Pre-Doctrine Test Stabilization mission: the 20,227-test run and 138-failure count captured against the NFR-001 gate.'
doc_status: deprecated
updated: '2026-06-15'
---
# Post-Mission Test Baseline: 01KSMG8Y

**Mission**: Pre-Doctrine Test Stabilization
**Date**: 2026-05-27
**Branch**: feat/pre-doctrine-stabilization-remediation
**Merge commit**: 56de9d565
**Gate**: ≤75 failures (NFR-001)

## Summary

| Metric | Value |
|--------|-------|
| Total tests | 20227 |
| Passed | 19534 |
| Failed | 138 |
| Errors | 2 |
| Skipped | 93 |
| xfailed | 18 |
| Run time | 873 s (14m 33s) |
| **Gate met** | ❌ NO (138 failures vs. ≤75 threshold) |

**Pre-mission baseline**: ~249 failures
**Reduction achieved**: ~111 fewer failures (249 → 138)

## Failure Clusters

| Cluster | Count | Notes |
|---------|-------|-------|
| `tests/specify_cli/test_command_template_cleanliness.py` (checklist) | 9 | Checklist skill package absent — tracked in #1317 (re-deferred) |
| `tests/specify_cli/invocation/cli/` (advise/do/profiles/invocations) | 21 | Invocation CLI regressions; T037 partial fix |
| `tests/cross_cutting/encoding/test_encoding_validation_cli.py` | 9 | Encoding validation CLI — pre-existing |
| `tests/cross_cutting/versioning/` + `test_version_isolation_integration.py` | 10 | Version detection/isolation — pre-existing |
| `tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py` | 7 | Finalize bootstrap regressions |
| `tests/specify_cli/skills/test_command_renderer.py` (snapshots) | 8 | Codex/vibe snapshot drift |
| `tests/tasks/test_planning_workflow_integration.py` | 9 | Planning workflow integration |
| `tests/tasks/test_tasks_support.py` | 5 | Task support regressions |
| `tests/specify_cli/test_acceptance_regressions.py` | 6 | Acceptance regression tests |
| `tests/next/test_prompt_file_invariant.py` | 3 | Prompt-file invariant (WP05 T019 side-effect) |
| `tests/specify_cli/next/test_runtime_bridge_documentation_composition.py` | 1 | Documentation composition test |
| Architectural / audit / misc | ~10 | Various pre-existing issues |
| `tests/missions/test_mission_switching_integration.py` | 2 | Mission switching (T040 partial fix) |
| Other (integration, e2e, cross_cutting) | ~8 | Pre-existing / environment-specific |

## Failure List

```
ERROR tests/contract/test_packaging_no_vendored_events.py::test_wheel_does_not_contain_vendored_spec_kitty_events
ERROR tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path
FAILED tests/agent/test_context_validation_unit.py::TestContextDetection::test_detect_false_positive_worktree
FAILED tests/agent/test_context_validation_unit.py::TestEdgeCases::test_detect_without_repo_markers
FAILED tests/architectural/test_docs_cli_reference_parity.py::test_visible_paths_match_reference
FAILED tests/architectural/test_no_dead_modules.py::test_no_new_dead_modules_under_src
FAILED tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported
FAILED tests/architectural/test_no_shipped_layer_label.py::test_doctrine_pack_validate_has_no_shipped_layer_label
FAILED tests/architectural/test_pytest_marker_correctness.py::test_fast_marker_must_not_apply_to_subprocess_users
FAILED tests/audit/test_audit_architecture.py::test_missing_evidence
FAILED tests/audit/test_no_legacy_agent_profiles_path.py::test_no_legacy_agent_profiles_path_literals_in_active_codebase
FAILED tests/cli/commands/test_intake.py::test_intake_file_content_in_brief
FAILED tests/cli/commands/test_intake.py::test_intake_file_writes_artifacts
FAILED tests/cli/commands/test_intake.py::test_intake_force_overwrites
FAILED tests/cli/commands/test_intake.py::test_intake_no_force_exits_1
FAILED tests/cli/commands/test_intake.py::test_intake_show_no_brief_exits_1
FAILED tests/cli/commands/test_intake.py::test_intake_show_prints_full_brief_hash
FAILED tests/cli/commands/test_intake.py::test_intake_stdin
FAILED tests/contract/test_packaging_no_vendored_events.py::test_vendored_events_tree_does_not_exist_on_disk
FAILED tests/cross_cutting/dashboard/test_dashboard_cli_accuracy.py::TestDashboardErrorMessages::test_error_message_helpful_when_not_initialized
FAILED tests/cross_cutting/dashboard/test_dashboard_cli_accuracy.py::TestDashboardProcessLifecycle::test_dashboard_process_actually_starts
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestCLIErrorHandling::test_command_with_nonexistent_feature
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestCLIOutputFormatting::test_fix_output_shows_summary
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestCLIOutputFormatting::test_output_includes_file_details
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestDetectIssuesWithoutFix::test_detect_issues_without_fix_exits_1
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestFixIssuesWithBackup::test_fix_creates_backup
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestFixWithoutBackup::test_no_backup_flag_skips_backup
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestValidateAllFeatures::test_fix_all_features
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestValidateAllFeatures::test_validate_all_features
FAILED tests/cross_cutting/encoding/test_encoding_validation_cli.py::TestValidateCleanFeature::test_validate_clean_feature_exits_0
FAILED tests/cross_cutting/misc/test_tasks_cli_commands.py::test_acceptance_commands
FAILED tests/cross_cutting/test_version_isolation_integration.py::test_cli_uses_source_version
FAILED tests/cross_cutting/test_version_isolation_integration.py::test_parallel_test_execution_isolated
FAILED tests/cross_cutting/test_version_isolation_integration.py::test_subprocess_inherits_isolation
FAILED tests/cross_cutting/test_version_isolation_integration.py::test_test_mode_requires_version_override
FAILED tests/cross_cutting/test_version_isolation_integration.py::test_version_checker_respects_test_mode
FAILED tests/cross_cutting/versioning/test_version_detection.py::TestEdgeCases::test_cli_version_flag_exists
FAILED tests/cross_cutting/versioning/test_version_detection.py::TestEdgeCases::test_version_does_not_crash_on_import
FAILED tests/cross_cutting/versioning/test_version_detection.py::TestRegressionPrevention::test_cli_reports_current_version_not_old
FAILED tests/cross_cutting/versioning/test_version_detection.py::TestVersionConsistency::test_version_via_cli_command
FAILED tests/cross_cutting/versioning/test_version_detection.py::TestVersionReading::test_cli_version_matches_package_metadata
FAILED tests/e2e/test_cli_smoke.py::TestFullCLIWorkflow::test_create_feature
FAILED tests/e2e/test_cli_smoke.py::TestFullCLIWorkflow::test_full_workflow_sequence
FAILED tests/e2e/test_cli_smoke.py::TestFullCLIWorkflow::test_setup_plan
FAILED tests/e2e/test_upgrade_post_state.py::test_upgrade_then_branch_context_does_not_gate
FAILED tests/init/test_init_minimal_integration.py::TestWP01InitCoherence::test_init_creates_agents_skills_for_codex
FAILED tests/integration/sparse_checkout/test_merge_preflight_blocks.py::TestMergePreflightBlocks::test_sparse_repo_blocks_merge
FAILED tests/integration/sparse_checkout/test_merge_with_allow_override.py::TestMergeWithAllowOverride::test_override_audit_log_carries_resolved_actor_not_unknown
FAILED tests/integration/sparse_checkout/test_merge_with_allow_override.py::TestMergeWithAllowOverride::test_override_flag_is_wired_from_cli_to_preflight
FAILED tests/integration/test_clean_install_next.py::test_clean_install_next_runs_without_runtime
FAILED tests/integration/test_legacy_feature_alias.py::test_charter_lint_help_does_not_mention_feature_flag
FAILED tests/integration/test_legacy_feature_alias.py::test_charter_lint_offers_canonical_mission_option
FAILED tests/integration/test_mission_review_contract_gate.py::test_mission_review_fails_when_done_wp_latest_review_artifact_is_rejected
FAILED tests/integration/test_quickstart_end_to_end.py::TestStep2_PreflightBlocksAndAutoRefresh::test_step2_preflight_json_blocks_with_reason
FAILED tests/migration/test_mission_state_repair.py::test_repair_canonicalizes_historical_meta_and_status_events
FAILED tests/migration/test_teamspace_migration_rehearsal.py::test_teamspace_mission_state_rehearsal_is_deterministic_across_clones
FAILED tests/missions/test_mission_schema_unit.py::TestGetMissionForFeature::test_raises_when_no_kittify_dir
FAILED tests/missions/test_mission_switching_integration.py::test_mission_switch_blocked_by_worktrees_via_cli
FAILED tests/missions/test_mission_switching_integration.py::test_mission_switch_shows_helpful_error
FAILED tests/next/test_prompt_file_invariant.py::TestBuildPromptOrError::test_returns_error_when_path_missing_on_disk
FAILED tests/next/test_prompt_file_invariant.py::TestBuildPromptOrError::test_returns_error_when_path_stat_raises_oserror
FAILED tests/next/test_prompt_file_invariant.py::TestBuildPromptOrError::test_returns_path_when_prompt_exists
FAILED tests/next/test_query_mode_unit.py::TestBuildPromptSafe::test_build_prompt_safe_suppresses_stdout_noise
FAILED tests/research/test_research_workflow_integration.py::test_full_research_workflow_via_cli
FAILED tests/runtime/test_paths_unit.py::test_locate_project_root_no_marker
FAILED tests/specify_cli/charter_preflight/test_cli.py::test_hard_error_exits_two
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestBootstrapStatsInJson::test_json_output_includes_bootstrap_stats
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestFinalizeTasksCallsBootstrap::test_bootstrap_called_after_dependency_parsing
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestTypedFrontmatterMigration::test_finalize_reads_wp_via_typed_reader
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestTypedFrontmatterMigration::test_finalize_updates_branch_fields_via_typed_api
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestTypedFrontmatterMigration::test_ownership_manifest_receives_typed_metadata
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestWP01Regressions::test_finalize_commits_status_and_snapshot_artifacts
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestWP01Regressions::test_finalize_rejects_incomplete_tasks_md_wp_coverage
FAILED tests/specify_cli/cli/commands/agent/test_feature_finalize_bootstrap.py::TestWP01Regressions::test_json_reports_modified_unchanged_preserved
FAILED tests/specify_cli/cli/commands/test_charter_interview_org_prefill.py::test_interview_without_org_packs_has_no_pre_fill
FAILED tests/specify_cli/docs/test_trail_model_doc.py::test_changelog_unreleased_has_both_tranches
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestDispatchMissingProfile::test_missing_profile_exits_1
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestDispatchNoCharter::test_no_charter_governance_context_unavailable_exits_zero
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestDispatchWithExplicitProfile::test_exits_zero_and_returns_json_payload
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestProfileInvocationComplete::test_complete_already_closed_exits_zero_with_warning
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestProfileInvocationComplete::test_complete_closes_record
FAILED tests/specify_cli/invocation/cli/test_dispatch.py::TestProfileInvocationComplete::test_complete_only_needs_invocation_id
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_empty_log_returns_empty_array
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_limit_caps_results
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_no_events_dir_returns_empty
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_profile_filter_reads_content_not_filename
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_status_open_vs_closed
FAILED tests/specify_cli/invocation/cli/test_invocations.py::TestInvocationsListJSON::test_three_records_returns_three
FAILED tests/specify_cli/invocation/cli/test_profiles.py::TestAgentProfileCompatibilityAlias::test_agent_profile_list_json_routes_to_profiles_list
FAILED tests/specify_cli/invocation/cli/test_profiles.py::TestProfilesListJsonOutput::test_exits_zero_and_returns_valid_json
FAILED tests/specify_cli/invocation/cli/test_profiles.py::TestProfilesListJsonOutput::test_json_output_has_required_fields
FAILED tests/specify_cli/invocation/cli/test_profiles.py::TestProfilesListJsonOutput::test_json_output_includes_fixture_profiles
FAILED tests/specify_cli/invocation/cli/test_profiles.py::TestProfilesListNoProfiles::test_no_profiles_json_returns_empty_array
FAILED tests/specify_cli/migration/test_schema_version.py::test_check_compatibility_cli_outdated
FAILED tests/specify_cli/next/test_runtime_bridge_documentation_composition.py::test_documentation_in_composed_actions
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[codex-charter]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[codex-implement]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[codex-tasks]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[codex-tasks-packages]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[vibe-charter]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[vibe-implement]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[vibe-tasks]
FAILED tests/specify_cli/skills/test_command_renderer.py::test_snapshot[vibe-tasks-packages]
FAILED tests/specify_cli/test_acceptance_regressions.py::TestIntegrationBranchGuard::test_branch_2x_no_merge_guidance
FAILED tests/specify_cli/test_acceptance_regressions.py::TestIntegrationBranchGuard::test_branch_main_no_merge_guidance
FAILED tests/specify_cli/test_acceptance_regressions.py::TestIntegrationBranchGuard::test_feature_branch_still_gets_merge_guidance
FAILED tests/specify_cli/test_acceptance_regressions.py::TestIntegrationBranchGuard::test_pr_mode_integration_branch_no_push_branch
FAILED tests/specify_cli/test_acceptance_regressions.py::TestIntegrationBranchGuard::test_well_known_branch_without_meta_target
FAILED tests/specify_cli/test_acceptance_regressions.py::test_perform_acceptance_persists_accept_commit
FAILED tests/specify_cli/test_cli/test_map_requirements.py::TestFinalizeTasksWithFrontmatterRefs::test_finalize_reads_requirement_refs_from_frontmatter
FAILED tests/specify_cli/test_cli/test_map_requirements.py::TestFinalizeTasksWithFrontmatterRefs::test_frontmatter_takes_priority_over_stale_tasks_md
FAILED tests/specify_cli/test_codebase_sweep.py::test_no_direct_meta_json_writes_outside_feature_metadata
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_has_feature_flag_guidance[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_has_yaml_frontmatter_with_description[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_no_057_mission_slug[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_no_absolute_user_paths[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_no_dev_specific_mission_slugs[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_no_kittify_missions_read_instruction[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_no_planning_repository_terminology[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_template_exists[checklist]
FAILED tests/specify_cli/test_command_template_cleanliness.py::test_template_minimum_length[checklist]
FAILED tests/specify_cli/test_no_checklist_surface.py::test_no_checklist_command_string_in_scan_roots
FAILED tests/tasks/test_planning_workflow_integration.py::test_check_prerequisites_ambiguous_context_returns_candidates
FAILED tests/tasks/test_planning_workflow_integration.py::test_check_prerequisites_works_in_main
FAILED tests/tasks/test_planning_workflow_integration.py::test_create_feature_in_main_no_worktree
FAILED tests/tasks/test_planning_workflow_integration.py::test_finalize_tasks_ambiguous_context_returns_candidates
FAILED tests/tasks/test_planning_workflow_integration.py::test_full_planning_workflow_no_worktrees
FAILED tests/tasks/test_planning_workflow_integration.py::test_setup_plan_ambiguous_context_returns_candidates
FAILED tests/tasks/test_planning_workflow_integration.py::test_setup_plan_explicit_feature_reports_spec_path
FAILED tests/tasks/test_planning_workflow_integration.py::test_setup_plan_in_main
FAILED tests/tasks/test_planning_workflow_integration.py::test_setup_plan_missing_spec_reports_absolute_path
FAILED tests/tasks/test_tasks_support.py::test_find_repo_root_malformed_worktree_git_file
FAILED tests/tasks/test_tasks_support.py::test_find_repo_root_no_git
FAILED tests/tasks/test_tasks_support.py::test_find_repo_root_normal_repo
FAILED tests/tasks/test_tasks_support.py::test_find_repo_root_walks_upward
FAILED tests/tasks/test_tasks_support.py::test_find_repo_root_worktree_with_subdirs
```

## Sub-issue Resolution

| Issue | Status | Notes |
|-------|--------|-------|
| #1301 | Closed (pending PR merge) | WP07 — shared-package events drift; commit 56de9d565 |
| #1302 | Closed (pending PR merge) | WP01 — TOML escape fix + twelve-agent snapshot refresh; commit 56de9d565 |
| #1303 | Closed (pending PR merge) | WP08 — charter synthesizer determinism + path_guard chokepoint; commit 56de9d565 |
| #1304 | Closed (pending PR merge) | WP03 — doctrine/glossary anchors + tactic schema repair; commit 56de9d565 |
| #1305 | Closed (pending PR merge) | WP06 — `next` CLI exit-code contract (pre-existing correct; docstring added); commit 56de9d565 |
| #1306 | Closed (pending PR merge) | WP04 — status/lifecycle event drift; protected-branch commit exception; commit 56de9d565 |
| #1307 | Closed (pending PR merge) | WP05 — charter integration regressions (6 tests); commit 56de9d565 |
| #1308 | Closed (pending PR merge) | WP02 — README Governance section; commit 56de9d565 |
| #1309 | Closed (pending PR merge) | WP02 — wp_files.py frontmatter lane guard; commit 56de9d565 |
| #1310 | Partially closed (pending PR merge) | WP02 (doctrine removal) + WP09 (misc debt); re-deferred: #1317 (checklist skill), #1318 (schema-version wording) |

## Notes

**Gate NOT met**: 138 failures vs. ≤75 threshold. Reduction from ~249 to 138 (~44% improvement) was achieved, but the remaining failures fall into clusters not fully addressed by this mission's scope:

1. **Checklist template failures (9)**: `spec-kitty.checklist` skill package absent — tracked as #1317 (explicitly re-deferred per C-008).
2. **Invocation CLI failures (21)**: dispatch/profile/invocation tests — T037 fix in WP09 addressed the `mode_of_work` field but deeper routing regressions remain.
3. **Prompt-file invariant (3)**: New tests added by WP05 T019 (`_build_prompt_or_error` path) have edge-case failures in the error-handling branches.
4. **Version isolation / encoding (15)**: Pre-existing environment-specific failures unrelated to this mission's scope.
5. **Skills snapshots (8)**: Codex/vibe command renderer snapshots need refresh after WP01 template changes.
6. **Finalize bootstrap (7)**: Regressions in typed frontmatter migration path.
7. **Planning workflow integration (9)**: Repo-root detection failures in worktree context.

Per DIR-013, each remaining cluster requires a filed GitHub issue before being treated as accepted baseline context. Issues to file post-PR-merge as part of the T048 closeout.
