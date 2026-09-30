---
doc_status: active
updated: '2026-09-30'
---

# Dead-code review, first pass — Domain B: CLI surface

Part of the [dead-code review of 2026-09-30](../README.md). Analysed at `origin/main` `bd1577a3`.

## Domain summary

This domain has 192 candidates (56 vulture, 60 allowlist, 75 ruff, 1 unused param). The biggest single cleanup is `agent/workflow.py`'s F401 re-export block. **35 of its 40 F401 names are dead in production.** The other 5 (`_collect_status_artifacts`, `_commit_workflow_change`, `feature_status_lock`, `is_worktree_context`, `locate_work_package`) are live, because `workflow_executor.py` looks them up late through `_wf().<name>` / `w.<name>` (workflow_executor.py:75-87). That late lookup is also why the test patches on those 5 names **do intercept**.

I checked every test patch of the `workflow` module (25 patched names, across all four idioms plus the `f"{_WORKFLOW}.x"` form). None of them targets a dead re-export, so **the workflow.py patch surface has no vacuous patch.** The vacuous patch in this domain is elsewhere: `test_mission_create_phases.py:152` patches the now-uncalled `_persist_pr_bound_phase`. There are also two cases where a test keeps a dead twin alive: `_render_charter_context` in workflow.py, and `_spec_artifact_dirty_paths` in accept.py.

The four doctor siblings on the dead-module allowlist are confirmed live. Importing `doctor.app` registers the `bytecode`, `channel`, `env-file` and `provenance` commands, each from its own sibling module.

| Class | Count |
|---|---|
| DEAD | 70 (35 workflow re-exports are counted as 27 DEAD + 8 TEST-ONLY) |
| TEST-ONLY | 27 |
| API/DYNAMIC (keep-with-note) | 44 |
| FALSE-POSITIVE | 51 |
| **High-confidence DEAD** | **58** |

The estimated removable LOC for the High-confidence DEAD set is about 290. The biggest pieces are 65 LOC for the status migrate trio, 48 for `check_version_compatibility`, about 35 for the workflow re-exports, 36 for the two mission_setup_plan helpers, 22 for `_persist_pr_bound_phase` plus `_read_meta_for_pr_bound`, and 20 for `_resolve_verdict_commit_router`. Removing the TEST-ONLY set as well would add about 520 LOC of src plus their tests.

## Findings by module

### cli/commands/agent/workflow.py (F401 re-export block, lines 58-161)

These are grouped rows. For every name, the evidence comes from a scan script ([`raw/workflow-reexport-scan.txt`](../raw/workflow-reexport-scan.txt)) that looked for:
- `specify_cli.cli.commands.agent.workflow.<name>` strings
- `setattr(<any>, "<name>")` and `patch.object(<any>, "<name>")`
- `*workflow*.<name>` / `*wf*.<name>` attribute access
- multi-line `from ...agent.workflow import (...)`

It covered all of tests/ and src/. It was cross-checked against the attribute names that workflow_executor reads through `_wf()`.

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| workflow.py:59,63,81-124 | `MISSION_TYPE_RESEARCH`, `re`, `build_dependency_graph`, `dependency_readiness_for_wp`, `get_dependents`, `write_text_within_directory`, `get_deliverables_path`, `get_mission_type`, `build_review_prompt_metadata`, `validate_review_prompt_metadata`, `write_review_prompt_with_metadata`, `render_wp_review_antipattern_checklist`, `resolve_review_cycle_pointer`, `AgentAssignment` (runtime import; the TYPE_CHECKING one in executor is separate), `WorkPackageClaimConflict`, `WorkPackageStartRejected`, `start_implementation_status`, `start_review_status`, `append_activity_log`, `build_document`, `set_scalar` (21 imports) | DEAD | Zero hits via the workflow module in tests/src. They are not in the `_wf()` read set, and executor imports its own copies directly (for example executor:59-62). The `get_mission_type` patches target `tasks_module`/`runtime_bridge`, not workflow. | High | remove |
| workflow.py:144,146,148,154,155,156 | `_is_missing_canonical_status_error`, `_missing_canonical_status_message`, `_read_wp_events`, `_review_feedback_root`, `_shared_artifact_guidance`, `_workspace_contract_description` (aliased re-exports) | DEAD | Zero importers or patches via workflow. The underlying cores functions are live: executor imports them directly (executor:47-59) and cores calls them internally. | High | remove the aliases |
| workflow.py:143,145,149-153,161 | `_has_prior_rejection`, `_latest_review_feedback_reference`, `_render_isolation_banner`, `_render_resolved_agent_identity`, `_render_wp_prompt_wrapper`, `_resolve_review_feedback_context`, `_resolve_review_feedback_pointer`, `_write_prompt_to_file` | TEST-ONLY (shim import surface) | Importers only, no patches. They are in tests/integration/test_rejection_cycle.py:145 (x10), characterization/test_trio_pure_cores.py:41, agent/test_workflow_review_cycle_pointer.py:88,137,237, agent/test_workflow_feedback_pointer_2x_unit.py:182, agent/test_review_feedback_pointer_2x_unit.py:21, review/test_artifacts.py:217, specify_cli/.../test_workflow_render_helpers.py:13, integration/test_agent_identity_prompt.py:17, runtime/test_tmp_prompt_namespace.py:31,219. Production calls the cores/executor names directly, with frozen imports, so a future patch of `workflow._X` would be vacuous. | High | Repoint the tests to `workflow_cores` / `workflow_executor`, then remove. The module comment at :131-136 ("monkeypatch.setattr(workflow, ...) call sites resolve identically") is misleading for these names. |
| workflow.py:81,90,109,123,159 | `_collect_status_artifacts`, `is_worktree_context`, `feature_status_lock`, `locate_work_package`, `_commit_workflow_change` | FALSE-POSITIVE (live late-binding) | Read by executor through `_wf()`/`w.` (executor:128,448 and the `w.` reads). The patches are effective: test_wrapper_delegation.py:207,213, test_implement_single_resolution.py:153, git_ops/test_atomic_status_commits_unit.py:955, test_charter_lifecycle_gates.py:162, test_workspace_husk_resolution_1833.py:391, agent/test_workflow_review_lane_gate.py:405. | High | Keep. Add `# noqa: F401 — read via workflow_executor._wf()` to them and drop the per-file F401 ignore, so the other 35 stop hiding. |
| workflow.py:896 | `_render_charter_context` (function) | TEST-ONLY (dead twin) | The live path is `workflow_executor.render_charter_context_text` (executor:474, called at :1352,:2045). The twin is only exercised by tests/agent/test_workflow_charter_context.py:18,121-158 and tests/charter/test_every_load_delivery.py:336-337. Line 317 of that file already covers the live function. | High | Remove with those tests, or repoint test_workflow_charter_context to `render_charter_context_text`. |

### cli/commands/agent_retrospect.py

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| agent_retrospect.py:15,20,36,52-55,58,63 | `sys`, `Console`, `RetrospectiveActor`, `MissionIdentity`, `Mode`, `ModeSourceSignal`, `RecordProvenance`, `RecordValidationError`, `write_record` (imports) | DEAD | Each name appears once in the file (the import; `sys` also appears once in a comment at :393). Tests patch `agent_retrospect.{locate_project_root,resolve_mission_handle,apply_proposals,read_record,_create_empty_retrospective_record}`, and all of those are live. Nothing patches or imports these 9 via the module. | High | Remove, and drop F401 from ruff.toml:32. |
| agent_retrospect.py:206 | `_empty_synthesis_result` (function) | DEAD | No reference in src/tests. The tests define their own `_empty_result()` helper. | High | remove |

### cli/commands/agent/* (other)

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| agent/mission_create.py:589 | `_persist_pr_bound_phase` (function) | DEAD + **vacuous patch** | No src caller. `pr_bound` is now written by `core/mission_creation.py:1282-1283`. **test_mission_create_phases.py:152 `monkeypatch.setattr(seam, "_persist_pr_bound_phase", …)` is vacuous**, and :292/:302 test the dead helper. | High | Remove with the :152 patch and the :285-305 tests. This cascades to `mission_check_prerequisites._read_meta_for_pr_bound` (:400), whose only remaining users are the shim re-export (mission.py:231), test_wp06_meta_reader_sweep.py:126-130 and test_mission_shim_reexports.py `_BRANCH_CONTEXT`. |
| agent/status.py:786,816,824 | `_migration_result_to_dict`, `_status_style`, `_print_rich_migrate_output` | DEAD | Zero references outside their own definitions. The `migrate` command (:862) is now a "[REMOVED]" stub that prints an error, so these are residue of the removed WP14 migrate command (65 LOC). | High | remove |
| agent/mission_setup_plan.py:332 | `_emit_spec_missing` | DEAD | Zero references in src/tests/packs. | High | remove |
| agent/mission_setup_plan.py:118 | `_artifact_absent_at_placement` | DEAD | Only its own def and a module-docstring mention (:9). The test mention (test_mission_setup_plan_phases.py:8) is docstring only, with no call. | High | remove, and update both docstrings |
| agent/mission_setup_plan.py:88 | `TASKS_MD_FILENAME` (const) | DEAD | One occurrence in the file (the definition). | High | remove |
| agent/config.py:108 | `_project_agent_root` | DEAD | Zero references anywhere. `_project_agent_surface` (:116) superseded it. | High | remove |
| agent/tasks_verdict_persistence.py:255 | `_resolve_verdict_commit_router` | DEAD | No src caller. Tests mention it only in docstrings (test_review_durability_matrix.py:42,747). The `_DURABILITY_REASON_*` constants are consumed elsewhere (:531,:572). | High | Remove, and fix the test docstrings. |
| agent/tasks_mark_status.py:131,363 | `artifact_mutated` (dataclass field) | DEAD | Written `False` at :363 and never read. The only other hit is an unrelated dossier Literal. | High | remove |
| agent/mission.py:343-348 | `TASKS_MD_FILENAME`, `SETUP_PLAN_COMMAND_NAME`, `FINALIZE_TASKS_COMMAND_NAME`, `PROJECT_ROOT_NOT_FOUND(_MESSAGE)` (constants in the shim) | DEAD | Each has only its definition line in mission.py. Seam modules define their own copies. | High | remove |
| agent/mission.py:346 | `INVALID_WP_OWNED_FILES_KITTY_SPECS` | TEST-ONLY | Imported by tests/agent/test_finalize_tasks_owned_files_validation.py:9 and pinned in test_mission_shim_reexports.py:53. It is a local re-definition, not a re-export, so it could drift from the seam copy. | Medium | Re-export from the seam (mission_parsing) instead of redefining it. |
| agent/mission.py:324, agent/tasks.py:350 | `logger` | DEAD | No `logger.` use in either file, and no test patches. | High | remove (trivial) |
| agent/tasks_materialization.py:367 | `_persist_inline_subtask_status` | TEST-ONLY | Its only src mentions are comments (tasks.py:161, tasks_mark_status.py:649). It is tested in test_tasks_materialization.py:25,224-245. | High | Remove with its tests. Check `_materialize_inline_subtask_status` next: its only src caller is this function plus the tasks.py re-export. |
| agent/tasks_outline.py:200 | `_wp_id_exists` | TEST-ONLY | No src caller. It is tested at test_tasks_outline.py:25,264-286. | High | remove with tests |
| agent/mission_parsing.py:67 | `_parse_dependencies_from_tasks_md` | TEST-ONLY | A duplicate of `core.dependency_parser.parse_dependencies_from_tasks_md`, which is what finalize actually uses (mission_finalize.py:1073, tasks_finalize.py:219). It is tested at test_mission_parsing.py:65-83. | High | remove with tests |
| agent/context.py:7,10 | `Optional`, `Console` imports | DEAD | F401, with no patches of `agent.context.Console`. | High | remove |

### cli/commands/implement.py and implement_cores.py

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| implement_cores.py:716 (re-exported at implement.py:85) | `_resolve_claim_commit_target` | TEST-ONLY | Never called in src: the implement.py hits are the import plus comments at :1107/:1208/:1218. Its test uses are test_implement_placement_routing.py:43-80. It is also named in the gate set `_SEAM_FOLD_CALLEES` (tests/architectural/test_no_write_side_rederivation.py:485), which is stale. | High | Remove with its tests and drop it from `_SEAM_FOLD_CALLEES`, or wire it if the D11 fail-closed placement is meant to be the claim path (needs-owner-decision). |
| implement.py:346 | `_validate_base_ref` | TEST-ONLY | `implement()` inlines `_resolve_base_ref` plus `_raise_base_ref_unresolved` (:1621-1623). It is tested by test_implement_base_ref.py:25-98 (#1917) and tests/cli/commands/test_implement_base_flag.py:18-158. Stale docstring refs are at workspace/context.py:1100 and lanes/worktree_allocator.py:870. | High | Retarget the #1917 tests to `_resolve_base_ref`, then remove. |
| implement.py:375 | `_feature_dir_status_paths` | TEST-ONLY | Only test_implement.py:84-88 uses it. | High | remove with the test |
| implement.py:2288 | `_ensure_vcs_in_meta`, `find_wp_file` (`__all__`) | API (live intra-module) | Called at :2152 and :1471. They are allowlisted only because they are exported without a cross-file importer. | High | keep; dropping them from `__all__` clears the allowlist entries |

### cli/commands/accept.py, init.py, invocations_cmd.py, intake.py, helpers.py, misc

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| helpers.py:486 | `check_version_compatibility` | DEAD | No caller in src or tests. Every test hit is a string/docstring, and tests/cli_gate/test_legacy_version_checker_removed.py:54-64 asserts it is *not* used ("FIX 1"). | High | Remove, then audit `core.version_checker.{compare_versions,format_version_error}` for cascade. |
| accept.py:243 | `_spec_artifact_dirty_paths` | TEST-ONLY (dead twin) | The accept flow inlines the same union at :498-503. It is only exercised by test_accept_residual_partition.py:49,194 (the M2/T008 regression), so that test guards the twin, not the live path. | High | Repoint the test to the live flow or to `_coord_dirty_paths`, then remove. |
| init.py:1024 | `sys._specify_tracker_active = True` | DEAD | Written once and read nowhere in src/tests/packs ("legacy headings" flag). | High | remove |
| init.py:630 | `_resolve_mission_command_templates_dir` | TEST-ONLY | No src caller. Only tests/runtime/test_resolver_unit.py:940-1116 ("Init integration") uses it. | Medium | remove with tests, or needs-owner-decision |
| invocations_cmd.py:150 | `append_to_index` | TEST-ONLY | Its docstring says "Called by InvocationWriter.write_started()", which is false: the writer uses its own `_append_to_index` (invocation/writer.py:207,257). It is tested at test_invocations.py:33,138. | High | remove with tests, and drop the #470 entry |
| invocations_cmd.py:72 | `_read_last_line` | TEST-ONLY | `_read_completed_record` (:97, used at :284) replaced it. It is tested at test_invocations.py:32,174. | High | remove with tests |
| intake.py:43 | `MAX_BRIEF_FILE_SIZE_BYTES` | TEST-ONLY | A duplicate of `intake.scanner.DEFAULT_MAX_BRIEF_BYTES`, which is the one enforced. Only test_intake_size_cap.py:6-13 pins it. | High | Remove, and point the test at `DEFAULT_MAX_BRIEF_BYTES`. |
| doctor.py:195, _auth_login.py:85, _auth_logout.py:40 | `logger` / `log` | DEAD | Never used after definition, and no test patches. | High | remove (trivial) |
| research.py:8, validate_tasks.py:8 | `Optional` | DEAD | F401 | High | remove |
| validate_encoding.py:39, validate_tasks.py:55 | `project_root =` (F841) | FALSE-POSITIVE (side effect) | `get_project_root_or_exit` exits outside a project. | High | Keep the call and drop the binding. |
| step_tracker.py:17 | `status_order` (attr) | DEAD | No reader anywhere. | High | remove |

### orchestrator_api/commands.py

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| commands.py:753 | `_get_last_actor` | DEAD | Zero references in src/tests. | High | remove |
| commands.py:3973 | `StoreError` (local import) | DEAD | F401; not referenced in the function. | High | remove |
| commands.py:2065 | `_resolve_history_commit_args` | TEST-ONLY | test_commands_fail_closed.py:16,124 itself says append-history "no longer calls `_resolve_history_commit_args` at all". The tests at :90,:108 exercise the orphan. | High | remove with those tests; also the test_no_write_side_rederivation.py:735 note |

### dashboard/*

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| dashboard/templates/__init__.py:30 | `get_dashboard_html(mission_context=…)` | TEST-ONLY (unwired feature) | The handler serves `get_dashboard_html_bytes()` (handlers/api.py:30). Only test_templates.py, test_static.py and test_csp_conformance.py call this. The `initial-mission` island in index.html:17 is always `null`, and no JS reads it. | High | needs-owner-decision: wire mission injection, or remove the function plus the placeholder |
| dashboard/api_types.py:45,246,385 | `ErrorResponse`, `FeaturesListErrorResponse`, `DiagnosticsErrorResponse` (TypedDict) | DEAD | Each appears only as definition plus `__all__`. They are not used as a return type, not nested, and not in test_api_contract.py. | Medium | remove, or annotate the handlers' error paths with them |
| dashboard/diagnostics.py:9, handlers/base.py:10, handlers/features.py:10, lifecycle.py:19 | `Dict`, `Optional`, `Tuple` | DEAD | F401 | High | remove |

### shims/*

| file:line | symbol (kind) | class | evidence | confidence | action |
|---|---|---|---|---|---|
| shims/generator.py:66 | `_get_arg_placeholder` | DEAD | Zero references. m_2_1_4 migration (:239) inlines `AGENT_ARG_PLACEHOLDERS.get(...)`. | High | remove |
| shims/__init__.py:12,15 | `SkillRegistry` (module alias) | DEAD | No `shims import SkillRegistry` or `shims.SkillRegistry` anywhere. It also collides confusingly with the real class `specify_cli.skills.registry.SkillRegistry`. | High | remove the alias and its B-category entry |
| shims/registry.py:95,137,142 | `is_consumer_skill`, `get_consumer_skills`, `get_all_skills` | TEST-ONLY | Only tests/specify_cli/shims/test_registry.py uses them. Callers use the frozensets directly. | High | remove with tests (drop the #470 entries) |

## Stale allowlist rationales

| Gate / category | Entries | Evidence | Action |
|---|---|---|---|
| `_WIDENED_SCOPE_GRANDFATHERED_470` ("each entry wired or deleted in #633") | `helpers::check_version_compatibility` | Fully dead. Its own regression test asserts non-use; the FIX 1 retirement is complete. | delete the symbol and the entry |
| `_WIDENED_SCOPE_GRANDFATHERED_470` | `invocations_cmd::append_to_index` | The docstring's claimed caller (`InvocationWriter.write_started`) does not call it; the writer has its own `_append_to_index`. | delete |
| `_WIDENED_SCOPE_GRANDFATHERED_470` | `shims.registry::{is_consumer_skill,get_consumer_skills,get_all_skills}` | Test-only accessor functions; never wired. | delete with tests |
| `_WIDENED_SCOPE_GRANDFATHERED_470` | `agent.mission::{TASKS_MD_FILENAME,SETUP_PLAN_COMMAND_NAME,FINALIZE_TASKS_COMMAND_NAME,PROJECT_ROOT_NOT_FOUND_MESSAGE,logger}`, `agent.mission_setup_plan::TASKS_MD_FILENAME`, `agent.tasks::logger`, `doctor::logger`, `_auth_login::log`, `_auth_logout::log`, `intake::MAX_BRIEF_FILE_SIZE_BYTES` | Residue of the #2056 god-module split: seams redefine the constants, and the loggers have never been used. | delete all (INVALID_WP_OWNED_FILES_KITTY_SPECS → re-export instead) |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` | `shims::SkillRegistry` | A module alias with zero users, and a name collision with the real `SkillRegistry` class. | delete |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` | `dashboard.templates::get_dashboard_html` | Not legacy but an unwired feature: the mission-context injection was never called, and the handler uses the bytes variant. | owner decision: wire or delete |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` | `dashboard.api_types::{ErrorResponse,FeaturesListErrorResponse,DiagnosticsErrorResponse}` | Unused contract types. The other 13 api_types entries are nested field types or JS-contract types (test_api_contract.py), so their rationale holds. | delete these 3 |
| `_CATEGORY_B_GRANDFATHERED_LEGACY` | `_auth_doctor::*` (9), `_branch_strategy_gate::{GateDecision,GateOutcome}`, `implement::{_ensure_vcs_in_meta,find_wp_file}`, `dashboard.lifecycle::_write_dashboard_file` | All are live *intra-module* and are listed only because they sit in `__all__` with no cross-file importer (for example `_auth_doctor` is reached via auth.py:142 `doctor_impl`). This is not legacy debt. | Trim `__all__` to the true cross-module surface; the entries then drop out. |
| `_CATEGORY_A_SLICE_F_DEFERRED` | `dashboard.csp::DASHBOARD_CSP`, `dashboard.server::BackgroundPortReportError` | The "no runtime caller catches it" TODO is moot: the error is raised live (server.py:325-336) as a `StructuredError`, and the CSP constant is consumed by `send_csp_header`. "Target = 0 by Slice G" is unmet. | Drop both from `__all__` (or accept them as API) and close the TODO. |
| `_CATEGORY_C_MERGE_DECOMP_SHIM_REEXPORT_2057` | `consolidate::BaselineMergeCommitError` | Its only consumers via the shim are tests: test_baseline_module.py:54 (`as LegacyError`), test_1827_baseline_regression.py:37, consolidation/test_merge_done_recording.py:21. No src importer uses that path; migrate_cmd and executor import from `consolidation`. | Repoint the 2 tests, keep the identity test only if the shim is kept, otherwise delete. |
| `_CATEGORY_C_DOCTOR_AUTO_DISCOVERY_SEAM` + dead-modules `_CATEGORY_9_AUTO_DISCOVERED_DOCTOR_SIBLINGS` | 4 modules / 7 symbols | **Rationale holds.** `doctor.py:221-238` runs `pkgutil.iter_modules` + `importlib.import_module` + `getattr(module,"register")` at import time. I confirmed it at runtime: `doctor.app.registered_commands` contains `bytecode`, `channel`, `env-file` and `provenance`, with callbacks from those exact modules. The comments have drifted: the symbols comment says "All six symbols" (seven are listed), and the dead-modules comment says "the three siblings" (four are listed). The structural auto-exempt (#3508) would remove all of this. | keep, and fix the comment counts |
| (arch gate) `test_no_write_side_rederivation.py:485` `_SEAM_FOLD_CALLEES` | `_resolve_claim_commit_target` | This callee is never called in src, so the exemption covers nothing. | remove the entry when the helper goes |

## Notable patterns

1. **"Re-export shims for patch compatibility" outlive their patches.** workflow.py's WP02 comment promises that `monkeypatch.setattr(workflow, …)` still works. That is only true for the 5 names executor reads via `_wf()`. The cores/executor functions are imported *frozen* by executor (executor:47-62), so patching `workflow._has_prior_rejection` etc. would be vacuous today. The 8 remaining test-only shim names are a trap for future tests. The per-file `F401` ignore in ruff.toml:31-32 hides all 35 dead names; a narrow `# noqa: F401` on the 5 live names would let ruff see the rest.
2. **God-module decomposition leaves dead twins that tests keep alive.** Examples:
   - `_render_charter_context` vs `render_charter_context_text`
   - `_spec_artifact_dirty_paths` vs the inline union in accept.py
   - `_validate_base_ref` vs the inline `_resolve_base_ref`
   - `_parse_dependencies_from_tasks_md` vs `core.dependency_parser`
   - `_resolve_history_commit_args`
   - `_persist_pr_bound_phase` vs core's pr_bound write

   In each case the regression test (#1917, M2/T008, B-8) now guards the twin instead of the production path.
3. **Removed commands leave their renderers behind.** Examples: the `status migrate` table/dict helpers, `check_version_compatibility` (FIX 1), and `append_to_index`, whose docstring names a caller that does not call it.
4. **Allowlist conflates "exported but intra-module" with "dead".** Many B/A entries are live intra-module symbols carried because of over-broad `__all__`. Trimming `__all__` would shrink the ratchet honestly.
5. **Unwired forward features.** Examples: dashboard `mission_context` injection (a placeholder that is always `null`), the `shims.registry` accessor functions, and the api_types error envelopes.

## False positives (compact)

- `preserve_quotes` (charter/pack.py:308, glossary.py:773,856, init.py:512,808, dashboard/handlers/glossary.py:145): ruamel `YAML()` config attribute.
- `console._file` (implement.py:183): reset of Rich Console's private attribute. `no_color` / `_color_system` (console.py:154-155): Rich Console attributes. `caption` (tracker.py:1014): Rich Table attribute.
- `CliConsole.set_all_plain` (console.py:157): test-determinism seam, used by the test harness (7 test refs). Keep as API.
- `standalone_mode` param (orchestrator_api/commands.py:292): Click `main()` override signature; the value is deliberately replaced.
- workflow.py `_collect_status_artifacts`, `is_worktree_context`, `feature_status_lock`, `locate_work_package`, `_commit_workflow_change`: live via `workflow_executor._wf()`.
- Allowlist entries that are live intra-module or dynamic:
  - `_auth_doctor::*` (9)
  - `_branch_strategy_gate::{GateDecision,GateOutcome}`
  - `_doctrine_health::PackHealth`
  - `implement::{_ensure_vcs_in_meta,find_wp_file}`
  - `dashboard.lifecycle::_write_dashboard_file`
  - `dashboard.csp::DASHBOARD_CSP`
  - `dashboard.server::BackgroundPortReportError`
  - 13 nested/contract `dashboard.api_types` TypedDicts
  - the 7 doctor auto-discovery `register` / `run_*` symbols
- ERA001 (all 14): section-divider comments, prose, or regex-pattern comments, none of which are commented-out code. Files: _test_env_check.py:34, mission_parsing.py:74,83, charter/list_cmd.py:321, consolidate.py:933, decision.py:293/403/453/508/563/628, reconcile.py:60 (import hint), review/_issue_matrix.py:371.
- F841 `project_root` in validate_encoding.py:39 / validate_tasks.py:55: the call is needed for its exit side effect. Drop only the binding.
