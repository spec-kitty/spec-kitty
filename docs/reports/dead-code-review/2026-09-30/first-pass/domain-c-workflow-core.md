---
doc_status: active
updated: '2026-09-30'
---

# Dead-code review, first pass — Domain C: workflow core

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

## Domain summary

The workflow-core domain has a small set of truly unreferenced helpers, mostly private one-liners left behind when logic was inlined. Those are safe to delete: about 250 LOC. The dead code with more cleanup value is code that only tests still use. Three runtime paths have been replaced but kept alive by their own tests:
- `core/worktree.py`: `create_feature_worktree` / `create_wp_workspace` / `setup_feature_directory`, about 570 LOC. Its `.spec-kitty/` exclude writer (FR-016) is therefore not wired into the live lane allocator.
- The `core/vcs` `GitVCS`/`VCSProtocol` class, about 840 LOC, is reachable only through those dead worktree functions.
- The `move-task` checkbox rewriter in `core/subtask_rows.py`.

The repo's `_WIDENED_SCOPE_GRANDFATHERED_470` set has **no stale-ratchet**, and at least 8 of its entries in this domain are now live. Two of the specific checks in the brief also hold up:
- `status/emit.py`'s `sync_dossier` has **zero src callers**. Only 3 test call sites pass it, and it is residue of the retired sync transport.
- `acceptance.post_consolidation`'s "dispatched governed Op" rationale is hollow. The CI enforcer that is supposed to back it is wired into no workflow, and the guide gives no invocation for the op.

| Class | Table rows | ≈ symbols |
|---|---|---|
| DEAD | 29 | ~43 |
| TEST-ONLY | 49 | ~75 |
| API/DYNAMIC | 9 | ~14 |
| FALSE-POSITIVE | grouped | ~120 (17 `preserve_quotes`, 12 `display_category`, 18 ERA001, ~60 allowlist rows used inside their own module, counters, etc.) |
| **High-confidence DEAD** | **26** | **~40** |

**Estimated removable LOC (High-confidence DEAD only): ~250.** If the High-confidence TEST-ONLY "remove with tests" items are included (the core/worktree cluster, subtask_rows writers, context_validation env pair, `append_event_jsonl`, `filter_dossier_snapshots`, `is_*_branch`, `is_safe`, `_print_remediation_lines`, `get_active_mission`), add ~900 src LOC. The optional GitVCS class removal adds ~840 more.

Evidence method used for every row: `rg -n -w <name>` over `src/ tests/ packs/ scripts/ .github/ pyproject.toml .kittify/ docs/`, excluding the defining file. For allowlist rows, an AST count of `Name`/`Attribute` loads inside the defining module separated "unexported but used internally" from "unused". I also scanned every string-form `patch("specify_cli.<domain>...")` / `monkeypatch.setattr("...")` in tests against the target module. See the vacuous-patch note in Notable patterns.

## Findings by module

### status/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| status/emit.py:847, :1102 | `sync_dossier` (param of `emit_status_transition` / `_batch`) | DEAD | `rg sync_dossier src` hits only the two signatures and docstrings (`noqa: ARG001 -- fan-out retired by #677`). Callers are tests only: test_emit.py:1614, test_events_tail_concurrency.py:188,287. | High | remove both params and docstring lines; drop the kwarg at the 3 test sites |
| status/models.py:457 | `ReviewOverride.is_release_sentinel` (property) | DEAD | 0 refs anywhere. Its docstring cites reducer `_apply_annotation_delta`, which no longer exists in src. | High | remove (15 LOC) |
| status/models.py:15 | `Optional` (F401) | DEAD | Not used in the file; hidden by the ruff.toml:101 per-file F401 ignore. | High | remove the import and the per-file ignore |
| status/migrate_lifecycle_envelope.py:86 | `logger` (unused module logger) | DEAD | Only the definition line; no `logger.` use (AST loads=0). | High | remove |
| status/emit.py:235 | `append_event_jsonl` (fn) | TEST-ONLY | Tests: test_emit.py only. Its own header comment says production goes through `coordination.status_transition`. | High | remove with its tests (18 LOC and stale header comment) |
| status/preflight.py:63 | `filter_dossier_snapshots` (fn) | TEST-ONLY | tests/status/test_preflight.py and test_dossier_snapshot_no_self_block.py; already "demoted" from `__all__`. | High | remove with tests |
| status/transitions.py:103 | `_run_guard` (fn) | TEST-ONLY | Docstring says "retained for guard-equivalence tests". test_wp_state.py:323 compares `can_transition_to` against `_run_guard`, but both delegate to `WPState.guard_for`, so the test is **tautological**. | Medium | remove it and the equivalence test |
| status/wp_state.py:151 | `WPState.can_transition_to` (method) | TEST-ONLY | 53 refs in 5 test files, 0 in src (the gate uses `check_transition`). | Medium | remove with tests, or keep as the documented boolean API |
| status/cutover_eligibility.py:310 | `assert_birth_invariant_holds` (fn) | TEST-ONLY | Assertion helper used only by tests/specify_cli/migration/test_dogfood_corpus_backfilled.py. | Medium | move into tests/ |
| status/doctor.py:82 | `findings_by_category` (method) | TEST-ONLY | test_doctor.py and test_2960_blanked_runtime_slot.py only. | Low | needs-owner-decision (2 LOC) |
| status/wp_metadata.py:593, :598 | `_Builder.append_to_history` / `append_dependency` | TEST-ONLY | test_wp_metadata.py only; `history[]` is the retired frontmatter field. | Low | remove `append_to_history` along with the history retirement |
| status/verdict_vocab.py:57, :64 | `ArtifactVerdict`, `EmissionArtifactVerdict` (Literal aliases) | TEST-ONLY | Used in no annotation (AST loads=0); only test_verdict_vocab_single_source. | Low | keep-with-note, or annotate `to_event_verdict` etc. with them |
| status/adapters.py:237 | `reset_handlers` | API/DYNAMIC | Test-isolation seam used by 15 test files and conftest. | High | keep-with-note |
| status/_unsafe.py | `ALLOWED_CALLERS`, `append_event` | API/DYNAMIC | Governed unsafe-door ledger; enforced by test_status_unsafe_allowlist.py. | High | keep |

### consolidation/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| consolidation/executor.py:403, :1923 | `_MergeRunState.birth_cutover_result` (field) | DEAD | Written once at :1923 and never read, in src or tests (0 hits outside those 2 lines). | High | remove the field and the assignment |
| consolidation/conflict_classifier.py:135 | `_strip_trailing_newline` | DEAD | 0 refs anywhere. | High | remove |
| consolidation/conflict_resolver.py:62 | `has_unresolved` (property) | DEAD | 0 refs in src or tests. | High | remove |
| consolidation/push_preflight.py:82 | `TargetBranchSyncStatus.is_safe` (always-True property) | TEST-ONLY | Docstring says "Deprecated. Always returns True"; ADR 2026-06-05-1 deprecates it; only test_target_branch_preflight.py uses it. | High | remove with its test and update the ADR note |
| consolidation/preflight.py:315 | `_print_remediation_lines` | TEST-ONLY | 0 src callers; 3 test refs. | High | remove with tests |
| consolidation/ordering.py:211 | `display_merge_order` | TEST-ONLY | AST loads=0 in module; only test_ordering_bake_seam.py. | Medium | remove with tests; drop the allowlist row |
| consolidation/done_bookkeeping.py:645 | `_durable_done_wps_on_coordination_ref` | TEST-ONLY | 0 src calls (executor.py:1104 and coherence.py:310/333 only mention it in comments). 4 test files still assert the FR-007 resume invariant against it, so they cover a path production no longer runs. | Medium | needs-owner-decision: re-wire it into resume, or delete it and its tests |
| consolidation/reconciliation.py:1674, :1685 | `_final_authored_blobs`, `_final_authored_deletions` | TEST-ONLY | Docstrings: "kept as an independently testable/importable name; `_collect_authored` calls the combined walk directly". | Medium | remove; point tests/consolidation/test_reconciliation.py at `_final_authored_walk` |
| consolidation/git_probes.py:698 | `lane_integrated_by_tree_or_ancestry` | TEST-ONLY | AST loads=0. The allowlist itself says "docstring cross-reference only"; executor.py:2580 is a docstring. | Medium | remove with test, or wire |
| consolidation/state.py:248, :268 | `progress_percent`, `set_pending_conflicts` | TEST-ONLY | Test-only (test_merge_state_unit.py, test_merge_recovery.py). CLAUDE.md lists `progress_percent` as a property. | Medium | remove `set_pending_conflicts`; keep or remove `progress_percent` (owner) |
| consolidation/state.py:260 | `has_pending_conflicts` (persisted field) | API/DYNAMIC | Serialized in state.json and documented in docs/guides/how-to/recovery/*, but src only ever assigns `False` (the setter above is test-only), so the field is vestigial. | Medium | keep-with-note, or drop in a state schema bump |
| consolidation/rollback.py:134 | `RollbackReport.advanced_branches` | TEST-ONLY | test_rollback_authority.py only. | Low | needs-owner-decision |

### coordination/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| coordination/status_service.py:139 (+:51) | `EventLogWriteContract.legacy_lane_append` and enum `LEGACY_LANE_APPEND` | DEAD | 0 refs for either name; `_validate_write_contract` never branches on it. | High | remove both |
| coordination/status_service.py:305 | `append_event_log` (write door) | TEST-ONLY | 0 src callers; transaction.py:34 imports only `append_event_stream_log`. 42 refs in 16 test files; listed in test_status_unsafe_allowlist.py:93 `COORD_WRAPPER_DOORS`. | Medium | needs-owner-decision: fold tests onto `append_event_stream_log`, remove the door and shrink `COORD_WRAPPER_DOORS` |
| coordination/surface_authority.py:272, :315 | `_classify_noncommit_outcome`, `_exit_code_for` | TEST-ONLY | Module comment at :37-44 says they rejoin `__all__` "as the remaining commit-surface loci are wired (epic #2160)". | Low | wire it (#2160) or owner-decision |

### core/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| core/worktree.py:167, :348 (+ :37-345, :432-606) | `create_wp_workspace`, `create_feature_worktree`, `setup_feature_directory`, `_ensure_spec_kitty_exclude`, `_exclude_from_git`, `_existing_worktree_is_valid`, `_create_workspace_with_fallback`, `_compose_worktree_feature_dir` | TEST-ONLY | 0 src importers for all 8 names (`rg -w` each). CLAUDE.md: `implement` via `resolve_workspace_for_wp` is the only supported path. About 570 LOC. **FR-016 `.spec-kitty/` exclude is only called from these dead functions**; `rg '\.spec-kitty/' src` shows no writer in lanes/worktree_allocator.py. | High | remove the cluster and its tests (test_worktree.py x2, test_worktree_symlink_fallback.py, test_worktree_exclude_spec_kitty.py); **wire `_ensure_spec_kitty_exclude` into the lane allocator first**, or confirm FR-016 is moot |
| core/vcs/git.py:40-878, protocol.py | `GitVCS` / `VCSProtocol` methods: `remove_workspace`, `list_workspaces`, `get_changes`, `init_repo`, `_get_git_dir`, and effectively the whole class | TEST-ONLY | The only `vcs.<method>(` calls in src are in the dead core/worktree cluster (:227, :256, :276). ops.py:94 calls `get_vcs()` only as a probe and discards the result. git/destructive_guard.py:249 already calls `remove_workspace` "dead code, zero callers". The module-level `git_*`/`capture_branch_tip` functions are live and stay. | Medium | needs-owner-decision: delete the class and Protocol (~840+267 LOC) after the worktree cluster goes |
| core/vcs/detection.py:299 | `_clear_detection_cache` | API/DYNAMIC | Cache-reset test seam (tests/_support/git_template). | High | keep |
| core/subtask_rows.py:59, :195, :206 | `count_subtask_rows`, `count_wp_section_subtask_rows`, `uncheck_wp_section_subtask_rows` | TEST-ONLY | 0 src callers. The docstring claims `move-task --to planned` uses the uncheck writer, but tasks_move_task.py:2985/:3292 now re-blocks off the snapshot ("#2513-via-snapshot"). | High | remove with tests (tests/specify_cli/core/test_subtask_rows.py parts, test_uncheck_wp_section_subtask_rows.py, test_find_unchecked_tasks_canon.py usage); fix the module docstring |
| core/context_validation.py:265 | `require_either` (decorator) | DEAD | 0 refs in src or tests; ADR 1.x says "documentation only". | High | remove |
| core/context_validation.py:228, :290, :330 | `require_worktree`, `set_context_env_vars`, `get_context_env_vars` | TEST-ONLY | Only tests/agent/test_context_validation_unit.py. `SPEC_KITTY_CONTEXT` env is never read in src. Only `require_main_repo` is imported (consolidate, implement, next_cmd). | High | remove with tests (~93 LOC); drop them from `__all__` |
| core/git_ops.py:258 | `has_tracking_branch` | TEST-ONLY | tests/git_ops/test_git_ops.py only. | Medium | remove with tests |
| core/paths.py:366, :393, :689 | `resolve_with_context`, `check_broken_symlink`, `assert_worktree_supported` (+ `StatusReadUnsupported` :543, which only the last raises) | TEST-ONLY | AST loads=0 for the three functions; tests only. | Medium | remove with tests (~73 LOC) |
| core/worktree_topology.py:323 | `render_topology_text` | TEST-ONLY | tests/init/test_worktree_topology.py only; production uses `render_topology_json` (workflow_executor.py:1361). | Medium | remove with test |
| core/saas_sync_config.py:58 | `sync_active` | DEAD (sync residue) | 0 src callers. The #3980 allowlist note says its last caller was removed. CLAUDE.md names `sync_active()` as residue that does not gate the moment path. | High | remove with test_saas_sync_config cases; update docs/context/team-kitty.md:206 and docs/api/environment-variables.md:260 |
| core/tool_checker.py:28 | `install_hint` (param of `check_tool`) | DEAD | `noqa: ARG001`; one src caller (:70) passes it positionally, tests pass "hint". | Medium | drop the param and update 1 src and 2 test call sites |

### git/, gitignore_manager
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| git/commit_helpers.py:781 (+:774) | `_commit_output_is_empty_changeset` and `_EMPTY_CHANGESET_MARKERS` | DEAD | 0 refs in src or tests. Its docstring says "kept as a fallback" with no caller; `_staged_tree_is_empty` is the authority. | High | remove (~18 LOC) |
| gitignore_manager.py:455 | `GitignoreManager._read_text_no_follow` | DEAD | 0 refs anywhere. | High | remove |
| gitignore_manager.py:615, :517 | `protect_selected_agents`, `get_agent_directories` | TEST-ONLY | init.py uses only `protect_all_agents` (:181/:208/:325); these two are exercised by tests only. | Medium | remove with tests (~49 LOC) |
| git/commit_helpers.py:530 | `protected_branches` (fn) | TEST-ONLY | Docstring says it stays public for tests/git/protected_target_fixtures.py (test oracle). | Low | keep-with-note, or move into tests |
| git/sparse_checkout.py:106 | `any_active` (property) | TEST-ONLY | 5 test files, 0 src. | Low | keep (report API) |
| git/remote_probes.py:95; git/sparse_checkout.py:421 | `_reset_remote_branch_lookup_cache`, `_reset_session_warning_state` | API/DYNAMIC | Test-isolation cache resets. | High | keep |

### lanes/, workspace/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| lanes/compute.py:235 | `SURFACE_TAXONOMY` (tuple) | DEAD | AST loads=0 and 0 test refs. Only docs/architecture/execution-lanes.md:130 prose mentions it; the real mapping is the keyword dict below it. | High | remove and fix the doc sentence |
| lanes/branch_naming.py:794, :864 | `is_mission_branch`, `is_legacy_branch` | TEST-ONLY | tests/lanes/test_branch_naming.py, test_lane_naming_parsers.py, test_branch_naming_human_slug.py only. | High | remove with tests (~25 LOC) |
| lanes/branch_naming.py:737; workspace/root_resolver.py:73 | `reset_legacy_failover_warning`, `_reset_cache` | API/DYNAMIC | Test-isolation resets. | High | keep |

### migration/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| migration/rebuild_state.py:246 | `_read_wp_frontmatter_full` | DEAD | 0 refs anywhere. | High | remove (23 LOC) |
| migration/backfill_runtime_state.py:1562 | `backfill_runtime_state_repo` | TEST-ONLY | The CLI `migrate backfill-runtime-state` (migrate_cmd.py:1354) now calls `runtime_state_cutover.cutover_repo`; src mentions are "Mirrors ..." docstrings only. | Medium | remove with tests (54 LOC) |
| migration/backfill_runtime_state.py:2262 | `run_backfill_and_verify` | TEST-ONLY | No src caller, but docs/operations/cutover-flip-linked-worktree.md:53 tells operators to import it. | Medium | needs-owner-decision: retarget the runbook to `cutover_mission`, then remove |
| migration/backfill_runtime_state.py:2367 | `assert_zero_readers` (+`find_field_readers`) | TEST-ONLY | A one-time proof utility (WP07 history deletion); tests/unit/migration only. | Medium | move into tests/ |
| migration/rebuild_state.py:677/720; strip_frontmatter.py:188/189 | result counters `conflicts_found`, `events_kept`, `wps_processed`, `fields_stripped` | FALSE-POSITIVE | Result-object fields written by src and read by tests. | High | none |

### mission.py, mission_metadata.py, missions/, mission_brief.py
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| mission.py:389, :393, :417, :432, :436 | `Mission.get_validation_checks`, `has_custom_validators`, `get_mcp_tools`, `get_agent_context`, `get_command_config` | DEAD | 0 refs in src, tests, packs or docs for each name. | High | remove (~37 LOC) |
| mission.py:17 | `Dict, List, Optional, Tuple` (F401) | DEAD | `rg -w` finds these words only in docstrings; hidden by the ruff.toml:73 F401 per-file ignore. | High | remove the imports and drop F401/UP035 from that per-file ignore |
| mission.py:455 | `get_active_mission` | TEST-ONLY | Only tests/architectural/test_loop_aware_resolution.py:146 (AST target) and a docstring. ADR 1.x/2026-01-27-10 scheduled its removal at v1.0.0. | High | remove; retarget the loop-aware AST test |
| mission.py:988 | `discover_missions` | TEST-ONLY | Only tests/missions/test_mission_schema_unit.py. The `discover_missions` hits in src are `runtime.next._internal_runtime.discovery`'s own, different function. | Medium | remove with tests |
| mission.py:825 | `validate_deliverables_path` (105 LOC) | TEST-ONLY | 4 test files, 0 src. docs/plans/testing/test-suite-friction-audit.md:86 flags a "live security gap" in its contract. | Medium | needs-owner-decision: wire into the research deliverables flow or delete |
| mission.py:321, :397, :413 | `get_template`, `get_workflow_phases`, `get_path_conventions` | TEST-ONLY | 1-2 test files each. | Low | needs-owner-decision |
| mission_metadata.py:914 | `clear_coordination_metadata` | TEST-ONLY | mission_type.py:942 docstring says it was replaced by `flatten_coordination_metadata` because this function "never popped topology". | High | remove with tests |
| mission_metadata.py:1004, :813 | `get_change_mode`, `set_purpose_summary` | TEST-ONLY | Tests only; bulk_edit/gate.py:63 reads `change_mode` inline. | Medium | remove with tests, or wire `bulk_edit/gate.py` to `get_change_mode` |
| mission_metadata.py:832 | `set_change_mode` | API/DYNAMIC | The bulk-edit skill tells agents to call it via `python -c` (src/charter/offering/skills/spec-kitty-bulk-edit-classification/SKILL.md:92-100). | High | keep-with-note |
| missions/_read_path_resolver.py:1592 | `resolve_feature_dir_for_slug` | TEST-ONLY | 0 src callers. docs/development/reference/read-side-seam-classification.md:684 warns that importing it "would silently re-open the exact gap". 19 test files use it. | Medium | remove, retargeting tests to `placement_seam(...).read_dir(kind)` |
| missions/_archive.py:279 | `is_mission_archived` | TEST-ONLY | tests/integration/test_mission_archiving.py only. | Medium | remove with test, or wire into validation |
| missions/__init__.py | `PrimitiveExecutionContext`, `execute_with_glossary` (lazy C-006 shim) | TEST-ONLY | The only importers of `specify_cli.missions.<these>` are tests/agent/glossary/*. src uses `charter.primitives`. glossary_hook.py:34 says `execute_with_glossary` has "zero production call sites". | Medium | retarget tests to `charter.primitives` and drop the shim re-exports |
| mission_brief.py:273 | `clear_mission_brief` | TEST-ONLY | tests/cli/test_mission_brief.py only (issue #728 refers to it). | Low | needs-owner-decision |
| mission.py:195 | `__context` param of `model_post_init` | FALSE-POSITIVE | Pydantic hook signature. | High | none |

### policy/, post_merge/, acceptance/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| policy/commit_guard_hook.py:97 | `_detect_owned_files` | DEAD | 0 refs; live code calls `_detect_ownership_scope` (:73). | High | remove |
| post_merge/stale_assertions.py:667 | `_is_directly_inside_assert` | DEAD | 0 refs. The same high/medium confidence logic is inlined at :731-750. | High | remove (21 LOC) |
| policy/audit.py (whole module, 89 LOC) | `create_audit_event`, `append_audit_event`, `read_audit_events` | TEST-ONLY | 0 src importers; tests/policy/test_audit.py only. `policy-audit.jsonl` is written by nothing. | Medium | needs-owner-decision (see dead-module verdict below) |
| acceptance/__init__.py:800 | `_read_file` | DEAD | 0 refs. | High | remove |
| acceptance/gates_core.py:872 | `_git_ref_exists` | DEAD | 0 refs. | High | remove |
| acceptance/execution_context.py:174 | `GateExecutionContext.not_applicable_below` (PH-1 phase floor) | TEST-ONLY | 0 src callers, so no gate enforces the PH-1 "NOT_APPLICABLE_IN_PHASE" rule its module docstring (:33) promises. | Medium | wire it into the gates, or drop PH-1 from the contract |
| acceptance/post_consolidation.py (whole module) | `verify_deferred_invariants`, `raise_for_violations`, the result and violation types | TEST-ONLY | 0 src or packs callers, and no documented invocation (see dead-module verdict below). | Medium | needs-owner-decision |

### upgrade/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| upgrade/detector.py:50, :93 | `VersionDetector.detect_schema_version`, `get_needed_migrations` | DEAD | 0 refs in src or tests; callers use `detect_version` and `applicable_migrations`. | High | remove (~23 LOC) |
| upgrade/migrations/m_0_10_0_python_only.py:360 | `_detect_custom_modifications` | DEAD | 0 refs. | High | remove (19 LOC) |
| upgrade/migrations/m_3_2_0rc35_kittify_profile_handoff.py:44-45 | `MIGRATION_ID`, `TARGET_VERSION` | DEAD | AST loads=0 in module; test hits are other modules' same-named constants. | High | remove, or use them as `migration_id = MIGRATION_ID` like siblings |
| upgrade/migrations/m_2_0_11_install_skills:26, m_2_1_1_repair_skill_pack:15, m_3_0_2_restore_prompt_commands:29, m_3_1_1_direct_canonical_commands:31, m_3_2_0rc35_kittify_profile_handoff:42, m_3_2_0rc35_pi_letta_backfill:19 | `logger` (6 unused loggers) | DEAD | `rg -w logger <file>` gives the definition line only; `import logging` then becomes unused too. | High | remove |
| upgrade/migrations/m_2_0_11_remove_clarify_command.py:6 | `List` (F401) | DEAD | Unused; hidden by the ruff.toml:110 per-file ignore. | High | remove the import and the F401/UP035 ignore |
| upgrade/skill_update.py:297 | `replace_skill_file` | DEAD | Only hit is test_no_dead_symbols.py (allowlist); no tests, no callers. | Medium | remove (38 LOC) |
| upgrade/skill_update.py:130, :182 | `apply_text_replacements`, `exclude_paths` | TEST-ONLY | The module docstring presents them as a migration-authoring toolkit, but no migration uses them (the 7 importers use `find_skill_files` / `file_contains_any` / `write_skill_text`). | Medium | needs-owner-decision |
| upgrade/migrations/m_3_2_8_provision_kitty_env.py:129 | `NEVER_SEED_VARS` | TEST-ONLY | AST loads=0; the exclusion works by omission, and the constant only documents it (1 test). | Low | wire it as an assertion in the seeding loop, or keep-with-note |
| upgrade/registry.py:121 | `MigrationRegistry.get_by_id` | API/DYNAMIC | Test utility across 12 test files; documented in ADR 2.x/2026-01-30-19. | Low | keep-with-note |

### task_utils/
| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| task_utils/support.py:682 | `warn_on_missing` (param of `get_lane_from_frontmatter`) | DEAD | Its docstring says "Unused; retained for call-site compatibility"; the one src caller is acceptance/__init__.py:777. | Medium | drop the param and that kwarg |
| task_utils/support.py:537-553 | `authored_role`, `authored_agent_profile`, `authored_model` (WorkPackage props) | TEST-ONLY | The dashboard reads `view.authored.*` (scanner.py:1036), not these; only test_reconstruct_wp_view.py:555-579 reads them. | Low | needs-owner-decision |

## Stale allowlist rationales

1. **`_WIDENED_SCOPE_GRANDFATHERED_470` (test_no_dead_symbols.py:3674-3694) has no stale-ratchet.** `_compute_stale` covers only `_SYMBOL_ALLOWLIST`; the 470 set is filtered in `_apply_widened_scope_exemptions` (:3925) and never checked for entries that went live. These entries in this domain are live now:
   - `migration.mission_state::audit_invocation_disagreement`: wired at audit/engine.py:323 and _mission_state_doctor.py:507. The 20-line rationale comment above the set says it has "zero non-test callers", which is **false now**.
   - `mission_metadata::load_meta_strict`: orchestrator_api/commands.py:2232.
   - `ownership.frontmatter_source::InMemoryFrontmatterSource`: migration/mission_state.py:1608 and cli/commands/agent/tasks_finalize.py:346.
   - `upgrade.autocommit::commit_touched_checkout`: cli/commands/upgrade.py:1189 and upgrade/runner.py:576, via `autocommit.` attribute access.
   - `acceptance::logger`, `git.commit_helpers::logger`, `git.protection_policy::logger`: used inside their own modules, so the own-module rescue already exempts them and the entries are redundant.

   **Action:** add a stale check for the 470 set, delete these 7 entries, and rewrite the stale comment. Every other 470 entry in this domain maps to a DEAD or TEST-ONLY row above.
2. **Dead-module Cat-7 `specify_cli.policy.audit`** ("KEEP -> adopt-as-follow-up ... tracked in a follow-up issue"): the rationale names no issue number. The Cat-7 policy in the same file says "target = 0 by 4.0", and pyproject is at `4.0.0rc5`. Nothing writes `policy-audit.jsonl`. **Verdict: stale.** Decide before 4.0 GA: delete the module and tests/policy/test_audit.py, or wire it into the override paths (commit-guard, merge-gate, risk overrides).
3. **Dead-module Cat-8 `specify_cli.acceptance.post_consolidation`** ("dispatched governed Op"). The rationale cites `docs/guides/accept-and-merge.md#deferred-invariants...`, but the file is actually at `docs/guides/how-to/missions/accept-and-merge.md`. That guide (:106-122) says nothing about how to invoke the op: no command and no `dispatch --profile`. It also claims the CI enforcer `scripts/ci/check_dangling_deferrals.py` is "wired into `ci-quality.yml`'s `deferral-consistency-check` job", but `rg deferral .github` returns **nothing**, and no workflow, Makefile or test references the script. So neither the op nor its enforcer runs. **Verdict: stale and misleading.** Wire the CI job and document the invocation, or retire the module, the script and the deferral state.
4. **`_CATEGORY_A_SLICE_F_DEFERRED` rows for `migrate_lifecycle_envelope::{MigrationAction, MigrationManifest, MigrationRowResult}`** say "module not wired yet". The module is wired through `m_3_2_9_migrate_lifecycle_envelope` (the same category's own REMOVED note says so), and all three types are used inside the module (AST loads 2/5/3). **Action:** drop them from `__all__` and delete the 3 rows.
5. **`_CATEGORY_C_WP_IN_FLIGHT_COORDINATION_BRANCH`** ("production wiring tracked under Priivacy-ai/spec-kitty#1355/#1356"): these are pre-org-move tickets, and all three symbols are used inside their own modules (`CoordinationBranchResult` 5 loads, `coordination_branch_name` 1, `resolve_planning_branch_from_meta` 1). "WP in flight" no longer applies. **Action:** drop from `__all__` and delete the category. `coordination_branch_name` also overlaps `lanes.branch_naming.coord_branch_name` (branch_naming.py:687-691 calls itself "the mission-create coord-branch composer"), so consider consolidating the two.
6. **`_CATEGORY_C_TERMINUS_RECONCILIATION_5001`**: "External consumers land with the Epic #5001 follow-ups". Those follow-ups (#5020, #5022, #5046) have landed per CLAUDE.md, and no external consumer arrived. `lane_integrated_by_tree_or_ancestry` has **no** caller at all (the rationale admits "docstring cross-reference only"). The other five are used inside their modules. **Action:** remove `lane_integrated_by_tree_or_ancestry` (or wire it); drop the rest from `__all__` and retire the category.
7. **`_CATEGORY_C_TEAM_KITTY_LAUNCH_DEFAULTS_3980` `sync_active`**: "either wire a consumer ... or retire it with the next contract version bump". It is sync-transport residue with 0 callers, and CLAUDE.md forbids re-enabling sync. **Action:** retire it (DEAD row above). The three env constants are used inside their module; the "wire literal-list sites" TODO still applies, since core/secret_redaction.py:39 hardcodes `"SPEC_KITTY_SKIP_PRE_REVIEW_GATE"`.
8. **`_CATEGORY_B_GRANDFATHERED_LEGACY`** in this domain is a mix:
   - **Test-only** (remove with tests): `context_validation::{require_worktree, set_context_env_vars, get_context_env_vars}`, `core.git_ops::has_tracking_branch`, `core.paths::{assert_worktree_supported, check_broken_symlink, resolve_with_context}`, `worktree_topology::render_topology_text`, `consolidation.ordering::display_merge_order`, `mission_brief::clear_mission_brief`.
   - **Unreferenced entirely:** `context_validation::require_either`.
   - **Used inside their own module, so the fix is "drop from `__all__`":** `AcceptanceMode`, `EncodingBackupCollisionError`, the `conflict_classifier` rules/`RULES`/`Resolution`/`ClassifierRule`, `MergeAmbiguousStateError`, `detect_git_merge_state`, `ExecutionContext`/`CurrentContext`/`detect_execution_context`/`get_current_context`, `BranchResolution`, `GitPreflight*`, `worktree_topology` types, `sparse_checkout*` constants, `LANE_AUTO_REBASE_FAILED`, `SRC_FALLBACK_*`, `ownership.validation::*`, `lifecycle_events` constants, `find_wp_dependency_cycles`, `upgrade_probe` constants, `unified_bundle` constants, `MigrationDiscoveryError`.
9. **`_CATEGORY_C_MERGE_DECOMP_SHIM_REEXPORT_2057`**: all 8 domain entries are used inside their modules, so the category is really "drop from `__all__`". Minor: the `check_push_safety` SymbolKey is listed **twice** (test_no_dead_symbols.py, the two identical entries after `_is_assigned_mission_number`). That is harmless in a frozenset but is copy-paste noise.

## Notable patterns

- **Replaced paths kept alive by their own tests.** core/worktree `create_*` (replaced by `lanes/worktree_allocator` + `resolve_workspace_for_wp`), subtask checkbox rewriting (replaced by the event-sourced snapshot), `backfill_runtime_state_repo` (replaced by `cutover_repo`), `clear_coordination_metadata` (replaced by `flatten_coordination_metadata`), `_durable_done_wps_on_coordination_ref` (the resume path moved). Each still has a test suite asserting behaviour production no longer runs. In the worktree case this hides a **real wiring gap**: FR-016's `.spec-kitty/` exclude never reaches live lane worktrees.
- **Sync-retirement residue in the status write path.** Besides `sync_dossier`, the `ensure_sync_daemon` kwarg is threaded through emit.py (:846, :1101, :1513), work_package_lifecycle.py, orchestrator_api/commands.py and coordination/outbound.py:119, then passed to `fire_saas_fanout(..., ensure_daemon=...)`. No handler reads `ensure_daemon`: `rg ensure_daemon src` hits only the two producers, and zeitgeist_bridge ignores it. That is another inert parameter chain worth removing in the same pass. `sync_active()` is residue of the same kind.
- **Forward APIs that never got a caller:** `not_applicable_below` (PH-1), `_classify_noncommit_outcome`/`_exit_code_for` (#2160), `policy.audit`, `post_consolidation`, the `skill_update` toolkit, `validate_deliverables_path`. Several module docstrings describe these contracts as if they were enforced.
- **Tests that prove nothing:**
  - test_wp_state.py:323 checks `can_transition_to` against `_run_guard`, and both call the same `guard_for`, so the check is tautological.
  - The FR-007 resume and FR-016 exclude suites exercise functions production does not call.
  - String-form `patch("specify_cli.status.<X>")` sites in consolidation tests (get_wp_lane, resolve_lane_alias, has_non_bootstrap_status_history, read_events) all look effective, because the consumers import lazily inside the function (done_bookkeeping.py:209-210, preflight.py:356, reconciliation.py:1315).
  - No vacuous patch surface was found for the domain's test-only symbols; `rg "(setattr|patch)\(.*<name>"` returned nothing for each.
- **Allowlist rows that should be `__all__` deletions.** Most B/C allowlist rows here are symbols used inside their own module but exported without an importer. Dropping them from `__all__` clears the allowlist row with no code deletion.
- **Per-file ruff ignores hiding F401.** ruff.toml carries per-file `F401` ignores for mission.py, status/models.py and m_2_0_11_remove_clarify_command.py, and all flagged imports there are dead. Remove each ignore together with its import.
- **Stale docstring cross-references:** `_apply_annotation_delta` (models.py:463/555/568; no such function in src), the `move-task` uncheck claim in subtask_rows, "live worktree-creation path" in test_worktree_exclude_spec_kitty.py, and the accept-and-merge guide's CI-job claim.

## False positives (compact)

- `preserve_quotes` (17 sites) and `allow_duplicate_keys`: ruamel.yaml attribute configuration.
- `display_category` (12 sites in wp_state.py): an abstractmethod and its overrides.
- `capabilities` property on GitVCS/protocol: Protocol conformance. The class as a whole is a TEST-ONLY finding above.
- `colocate` params (git.py:695, protocol.py:231): Protocol signature with `noqa: ARG002`; they go if the class goes.
- `mission.py:195 __context`: pydantic `model_post_init` signature.
- `project_post_checkpoint_commits_to_target` / `ProjectionResult`: called at bookkeeping_projection.py:374 (vulture found no issue; this is allowlist-only).
- All 18 ERA001 hits (conflict_resolver:240, ordering:593, resolve:263, coordination/__init__ ×4, paths:175, mission_state:2455, rebuild_state:359, runtime_state_cutover:455, schema_version:194, inference:82, commit_guard:113, stale_assertions ×3, _unsafe:105): explanatory prose or section comments, not commented-out code.
- Result-object counters (`conflicts_found`, `events_kept`, `wps_processed`, `fields_stripped`): written by src, reported and read by tests.
- `authored_*` dict keys in dashboard/scanner.py are a separate surface from the WorkPackage properties (listed above as TEST-ONLY).
- Allowlist symbols used inside their own module: FP as dead code; only the `__all__` export is unused. See Stale allowlist rationales §8/§9 for the list.
- T3 re-export names `IntakeFileMissingError`/`IntakeFileUnreadableError` in mission_brief: intentional back-compat re-exports pinned by tests/specify_cli/test_error_backcompat.py (keep).
