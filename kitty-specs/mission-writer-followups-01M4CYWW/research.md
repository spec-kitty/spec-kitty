# Research: mission-writer-followups

Brownfield scout squad on branch `issue-5883-mission-writer-followups` (stacked on PR #5890), 2026-10-08. There were three read-only lenses: writers, runtime and templates, and pack, wording and glossary. Line numbers are as of that HEAD.

## R1 — Lock key (rekey)

- `mission_write_lock(feature_dir)` keys on `feature_dir.name` (`status/mission_write.py:97`).
- `BookkeepingTransaction` keys on `_mission_specs_dir_name(slug, mid8)` = `coord_mission_dir_name` (`coordination/transaction.py:567`, `branch_naming.py:645-673`): `slug if slug.endswith(f"-{mid8}") else f"{slug}-{mid8}"`.
- `coord_status_lock` keys on the coord dir name (`status_transition.py:436`); emit on `canonical_feature_dir.name` (`emit.py:977`).
- **Divergence.** A legacy primary dir `060-test` whose meta records `coordination_branch` and mid8 `01COORD0` is a case where the transaction locks `060-test-01COORD0` while `ensure_vcs_locked`, `hold_mission_write_lock(ctx.mission_dir)` (`implement_phases.py:415`) and emit on the primary dir lock `060-test`. `mission_write_lock_dir` (`_read_path_resolver.py:1865-1880`) uses an existence-aware resolver, so its answer depends on whether the coord worktree resolves.
- **Decision.** D1 in the plan adds one pure key function, read from `meta.json`. Its callers:
  - `mission_write_lock`: `review/cycle.py:1117/:1163/:1204`, `lanes/implement_support.py:1032`, `implement_phases.py:415`, `workflow_executor.py:230/:1085/:1888`, `status_transition.py:436`, `retrospective/tracer_writer.py:322`.
  - `mission_write_lock_dir`: `review/cycle.py:1116/:1162`, `agent/tasks.py:1198`, `tracer_writer.py:322`.

## R2 — meta.json read-modify-writes (FR-001, FR-020)

Each setter in `mission_metadata.py` reads with `_require_meta`/`load_meta` and writes with `write_meta` (atomic, `:600`). None takes a lock.

| Writer | Caller | Lock today |
|---|---|---|
| `record_acceptance` :682/:722 | acceptance/__init__.py:1669 (planning-only) and :1682 | none at :1669; :1682 sits inside `locked_acceptance_verdict_guard` (keyed on the coord dir name) |
| accept direct restamp | acceptance/__init__.py:1771-1776, :1840-1845 | none |
| `record_discard` :726 | mission_type.py:967 ← close_cmd :622 | none |
| `flatten_coordination_metadata` :967 | mission_type.py:945; _coordination_doctor.py:1059; consolidation/phase_teardown.py:138 | none (consolidation holds only the global merge lock) |
| `clear_merge_metadata` :909 | mission_type.py:1491 (reopen) | none |
| `set_target_branch` :821 | mission_finalize_branch_contract.py:364 | none |
| `set_origin_ticket` :786 | tracker/origin.py:145 | none |
| `set_documentation_state` :773 | core/mission_creation_meta.py:204 | none |
| `set_vcs_lock` :756 | implement_support.py:1038 | locked (`ensure_vcs_locked` :1032, unbounded) |
| `set_change_mode` :853, `clear_coordination_metadata` :938, `set_purpose_summary` :834 | no production caller; in `dead_symbol_allowlist.yaml` :1472/:1476/:1478 | — |

Other FR-020 writers, all unlocked today:
- finalize: `_persist_recovered_pr_bound_contract` (`mission_finalize_branch_contract.py:145-163`) and `restore_meta_text` (`mission_metadata.py:603/:631` ← `mission_finalize_commit.py:896`).
- documentation state: `doc_analysis/doc_state.py` `set_audit_metadata` :263 and `set_generators_configured` :233, used in production from `mission_setup_plan.py:914/:980`; plus `set_iteration_mode`, `set_divio_types_selected`, `write_documentation_state`, `ensure_documentation_state`.
- consolidation: `phase_teardown._clear_landed_single_branch_mission_branch` :488; `baseline.record_baseline_merge_commit` :122 and `_stamp_pr_merge_provenance` :764; `mission_number/bake.py` :359/:535 (scratch checkout)/:767/:807.
- the rest: mission loader (`mission_loader/command.py:351`), mission-state migration (`migration/mission_state.py:1743`), `migration/runtime_state_cutover.py:331`, `upgrade/feature_meta.py:61`, and the raw meta writes in `backfill_mission_type.py:94`, `backfill_identity.py:175/:338`, `backfill_topology.py:133` and `upgrade/migrations/m_0_13_8_target_branch.py:121`.

Near-miss: `consolidation/drivers.py:471` writes the merge driver's `ours` temp file.

## R3 — Frontmatter and matrix writers (FR-002..FR-005)

- map-requirements reads the merge base at `tasks_map_requirements.py:411` and re-reads at :513, but writes the stale planned value at :520/:525 with no lock (pipeline :857-863).
- finalize flush: `mission_finalize_bootstrap.py:458-463` (`_flush_frontmatter_writes`), called from `mission_finalize.py:997`, no lock. Also `tasks.md` at :687.
- finalize write-scope restore: snapshot at `mission_finalize.py:804/:814`; restore at :1430/:1448 through `mission_finalize_commit.py:1027` `_restore_mission_write_scope`. It blindly calls `write_bytes(original)` at :1058, keeping only status-commit files (:1070-1077).
- lane mirror: `emit.py:628` `_mirror_phase1_frontmatter_lane`. It is reached inside the emit lock (:977/:1153) and inside the transaction (`status_transition.py:1139` ← :1657). It is locked at runtime, but the write is not lexically inside a lock `with`.
- other frontmatter writers: `implement_support.py:491` `update_fields` (only the checkout claim lock is held); `task_metadata_validation.py:178`; `frontmatter.py:388/:403/:211`; migrations (`backfill_ownership.py:185`, `strip_frontmatter.py:181/:202`, `backfill_identity.py:412`, `m_2_0_6_consistency_sweep.py:211`). Near-miss: `review/prompt_metadata.py:219`.
- matrix: `scaffold_issue_matrix` (`tasks/issue_matrix.py:496`) runs its exists check at :555 and writes the whole map at :577/:579 with no lock. The helpers `acceptance/matrix.py:613/:796` and `issue_verdict.py:304` use `feature_status_lock(repo_root, matrix_dir.name)`:
  - **Root:** same common dir in practice; the paths only diverge on the degrade path, `locking.py:160-164`.
  - **Key:** `matrix_dir` is the write surface, so on coord it is `<slug>-<mid8>` while primary writers use `feature_dir.name`. That is the real divergence. The red test must confirm which of the two applies.

## R4 — Runtime terminal gate (FR-009..FR-011)

- Legacy path, `runtime_bridge.py`:
  - `_dn_decision_materialize` :1215. The capture runs at :1244-1265 when the policy blocks (`_dn_capture_pre_speculative_state` :1043-1059 plus `_BufferingRuntimeEmitter`).
  - `_dn_advance_engine` :1198-1212 calls `commit_advance` without the hook, or `runtime_next_step` when there is no plan or on `StaleAdvancePlan`.
  - The gate is checked only after the engine has written (:1288-1291). On refusal, `_dn_rollback_buffered_run_state` (:1062-1091) calls `write_bytes(pre_state)` and `truncate(pre_size)`.
- Composition path, `runtime_bridge_engine.py:266`: already uses `before_run_completed`. A refusal reads as the generic `_advance_failed_decision` (`runtime_bridge.py:888`).
- Engine:
  - `commit_advance` (`engine.py:599-627`) takes `before_run_completed`. It is called only on the transition into terminal (:549), which means re-polls are not gated.
  - `next_step` (:574-592) has no hook parameter. This is FR-011.
  - `_append_event` :104 is append-only. `_write_snapshot` :129 writes a tmp file and then calls `os.replace`.
- Typed refusal: `retrospective_hook.py:21 MissionCompletionBlocked`. Today `_run_retrospective_learning_capture` (`runtime_bridge_retrospective.py:357-412`) re-raises whatever exception it got.
- `_BufferingRuntimeEmitter` is at `runtime_bridge_retrospective.py:39-120`. Its tests are in `tests/runtime/test_bridge_decide_next.py`, `test_bridge_retrospective.py`, `test_bridge_decision_log_flush.py`, `test_bridge_no_compat_delegates.py` and `tests/next/test_runtime_bridge_unit.py`.

## R5 — Runtime templates (FR-018, C-008)

- Resolver: `runtime_bridge_io.py:611` `_runtime_template_key`. Tiers are at :631-642; software-dev puts the built-in tier before the global one.
- Built-in tier: `_build_discovery_context` :407-438 and `_builtin_missions_root` :491-504. Both do a bare `import specify_cli` and point at `specify_cli/missions`, with the comment "doctrine catalog is not behaviorally equivalent yet".
- Canonical accessor already importable from runtime: `charter.activation.mission_type_profile_repository.builtin_missions_root()` (:55).
- Drift between the copies:
  - **software-dev:** only the banner, comment paths, `agent-profile` on discovery/plan/tasks/implement/review, and "feature"→"mission" in the accept description. The step order is the same.
  - **documentation:** comments, plus an accept `agent-profile`.
  - **research:** comment only.
  - **plan:** the pack copy has no `mission.name`/`version` and no top-level `steps`, so it **does not load** (`schema.py:364-370`).
- Widening risk: `_should_dispatch_via_composition` (`runtime_bridge_composition.py:~170`) returns `bool(profile or contract_ref)`.
- #2652: `packs/built-in/missions` is canonical; only the type dirs retire later. `mission.yaml` and `templates/` are still read by `specify_cli/mission.py:79` and `charter/activation/neutrality/lint.py:380`. So only `mission-runtime.yaml` moves now.
- Ledger: `_RUNTIME_ALLOWED_SPECIFY_CLI` (`test_layer_rules.py:147-205`), cap 23 (`_baselines.yaml:22`). The `""` entry is the two bare imports. `test_runtime_ledger_has_no_stale_entries` (:1151) forces its removal (23 → 22).

## R6 — Drift, analyze currency and guards (FR-016, FR-017)

- Drift:
  - At start, `start_mission_run` (`engine.py:195-251`) freezes the template (`_freeze_template` :143-160) and records `template_path`/`template_hash` (`schema.py:504-507`).
  - `planner._check_template_drift` (:321-333) blocks when the live hash differs. `existing_template_path` (:304-309) returns None when the path is gone, and then drift is skipped. That is what keeps an in-flight run on its frozen order once the `src` copy is retired.
  - Workflow-composed runs record `key#workflow:id` and are never drift-checked.
- Currency: `analysis_report.check_analysis_report_current` (:559) returns `AnalysisFreshness` (`ok/stale/missing/reason/mismatches`). The reasons include `missing_analysis_report` and `stale_analysis_report`. The implement gate is `workflow.py:1246` (`_require_current_analysis_report`). `analysis_report` is not in the runtime ledger.
- Injection: `next_cmd.decide_next` (:61) → `runtime.next.decision.decide_next` (:325) → `decide_next_via_runtime` → `DecideNextContext` (`runtime_bridge.py:303-332`).
- Guards: `runtime_bridge_cores.py:749` `_evaluate_software_dev_guards` (`_GUARD_TABLES` :834). The refusal re-issues the step with `guard_failures` (`runtime_bridge.py:780-829`). JSON fields: `reason`, `guard_failures`, `guard_failure_paths`, optional `error_code` (`decision.py:93-192`).
- `analyze/step.yaml:10` has `in_action_sequence: false`, so it goes through the legacy DAG path and gets the D4 hook.
- Risk to check: `_dn_finalized_board_override` may hand out implement after finalize, skipping analyze.

## R7 — Pack software-dev cleanup inventory (FR-015, FR-022)

- **Wiring.**
  - Action sequence: specify(0), plan(1), tasks(2), implement(3), review(4). analyze, accept, charter, research and the tasks-* sub-steps are off-sequence.
  - All 12 step dirs are prompt-backed (`skills/command_installer.py:81-94`). `shims/registry.py:54-77` disagrees for tasks-finalize.
  - The legacy tasks_* ids fold into `tasks` (`runtime_bridge_composition.py:107-121`).
- **Pack files.**
  - `software-dev/mission-runtime.yaml:1-7`: deprecation banner (provenance 1).
  - `software-dev/README.md:81/:87/:95-109/:115`: stale 6-state workflow and 9-step DAG; nonexistent `command-templates/`.
  - `missions/README.md:11/:22`.
  - `mission.yaml:66/:71`: generic v1 text; it stays on src, and only wording is fixed in the pack copy.
  - `expected-artifacts.yaml`:
    - :37-38 and :44-64 are keyed on the retired tasks_* ids.
    - :44-48 contradicts the tasks-outline prompt.
    - :68-72 says implement never checks analysis-report.md.
    - Pinned by `tests/dossier/test_manifest_guard_parity.py` and `tests/runtime/next/test_*guard*`.
  - `governance-profile.yaml:5/:17` (kitty-specs path, WP ids).
  - `actions/*/index.yaml`: no analyze index.
  - `built_in_step_contracts/tasks.step-contract.yaml:18/:34`.
  - `step.yaml` chain: tasks-finalize depends on tasks, not tasks-packages; analyze has `depends_on: []`.
- **Per prompt.**
  - **tasks** (716 lines):
    - The report sections never make analyze required (:279/:596); only Step 10 does (:605-609), and staleness is never mentioned. :58 says next leads straight to implement.
    - Duplication: Outline :90-280 vs Steps :464-612, with step 2 missing; sizing rules three times (:153-169/:346-421/:435-460).
    - It tells agents to write tasks.md by hand (:178/:527) and refers to a template it never defines (:178/:199).
    - :308-309 give the same command for both dependency cases.
    - :470 contradicts :60. :582 edits after finalize.
    - Provenance at :133/:337; "feature" at :26-28/:122/:166-168/:389-393/:441/:716; version line :6.
  - **tasks-finalize:** analyze framed as optional (:163); :175 says next advances to implementation and has no `--mission`; retired term "planning repository" at :15/:17; :10/:38-39 parse dependencies from tasks.md; example path at :140-142; **no provenance baseline entry** (C-003 hazard).
  - **tasks-outline:** `prompt_file` examples (:137/:153/:170) contradict :184; :214 wrongly says next advances; "feature" at :20/:23/:72.
  - **tasks-packages:** :269 wrongly says next advances; duplicate command at :215-217; `/ad-hoc-profile-load` at :124/:128, also in implement:150/:348, review:123/:320 and task-prompt-template:31.
  - **analyze:** no staleness rule; Next Actions use bare `/implement` and `/plan` and suggest editing tasks.md by hand (:216-219); temp-file guidance :185 contradicts :211; provenance at :24.
  - **accept:** `cd $(git rev-parse --show-toplevel)` inside a worktree returns the worktree root, a bug (:21); version :6.
  - **implement:** :291 greps the retired `src/specify_cli/missions/*/command-templates/`; :183-184 cites a WP06 detail; never mentions the analysis gate.
  - **plan:** :58/:95 provenance; a `kitty-specs/charter-e2e-827-followups-01KQAJA0/...` citation; "feature" at :218-248.
  - **specify:** provenance at :189/:225/:268; "feature" at :437-469/:817-823. :246 is pinned by `test_specify_commit_example_subject.py`.
  - **tasks/guidelines.md:42:** hands off to implement with no analyze step.
- **Pins.**
  - `tests/specify_cli/test_command_template_cleanliness.py:396-408` (analyze whole-file asserts, ≥50 lines, `--mission`, "repository root checkout").
  - `tests/prompts/test_tasks_prompt_ownership_metadata.py:13-19/:48-89`.
  - `tests/contract/test_tasks_packages_prompt_guards.py`.
  - `tests/prompts/test_prompt_fragment_rendering.py:29-32`.
  - `tests/doctrine/missions/test_mission_steps_layout.py:53-63`.
  - `tests/specify_cli/cli/commands/test_analyze_surface_agreement.py:62`.
  - `tests/doctrine/test_builtin_cli_command_references.py`.
  - The provenance ratchet `tests/architectural/test_builtin_pack_provenance_ratchet.py` is shrink-only and tight. Refresh it with `python -m tests.architectural.test_builtin_pack_provenance_ratchet`. Baselines: tasks 9/57, tasks-outline 4/18, tasks-packages 5/12, tasks-finalize repo_paths 2 (no provenance entry), analyze 2/1.
  - `pack-manifest.yaml` does not hash prompts. `step.yaml` or action-index changes require `spec-kitty doctrine regenerate-graph` (roundtrip gate `test_doctrine_regenerate_graph_roundtrip.py`).

## R8 — "for feature" sites (FR-012..FR-014)

- **Builders:**
  - `mission_finalize_planning_pin.py:1162-1170` (used :552, `mission_finalize_commit.py:411`, re-exported `mission_finalize.py:198`)
  - `mission_setup_plan.py:258/:933/:993`
  - `core/mission_creation_commit.py:95`
- **Drift check:** `mission_finalize_planning_pin.py:1173-1209`. It does an exact match on one subject at :1198/:1209.
- **commitlint:** `commitlint.config.cjs:21` covers only meta, spec, tasks and plan subjects.
- **Errors:**
  - `status/uninitialized_hint.py:105/:107`, `task_utils/support.py:449`
  - `acceptance/__init__.py:1130/:1144`
  - `plan_validation.py:88`
  - `validate_tasks.py:128`, `validate_encoding.py:95`
  - Extra: `mission_branch_context.py:149` "Planning/base branch for this feature" (fold in).
- **Tests asserting the old text:**
  - `tests/specify_cli/test_canonical_acceptance.py:489`
  - `test_finalize_tasks_commit_surface.py:155`
  - `test_sc6_planning_placement_e2e.py:380/:400/:452`
  - `tests/cli/commands/test_agent_mission_commit_to_branch.py:140`
  - `tests/core/golden/mission_create_*.json`
  - `tests/tasks/conftest.py:119`

## R9 — Glossary (FR-021)

- **Surfaces:**
  - `docs/context/orchestration.md`: Mission :67-75, Mission Run :79-85, Feature :91-98, feature branch :396-404 (linked :376/:380/:465/:477/:489).
  - YAML seed `.kittify/glossaries/spec_kitty_core.yaml` (mission :318 is the Mission-Type meaning; feature branch :174).
  - Pack `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` (:382-386, :206-212; hashed in pack-manifest :355-356, so regenerate-graph).
  - Generated `src/specify_cli/.contextive/orchestration.yml` (`scripts/generate_contextive_glossaries.py`, currently stale).
- **Gates:** `test_glossary_pack_parity.py` (seed↔pack full key parity), `test_glossary_authority_parity.py`, `tests/glossary/test_seed_validation.py`, `test_no_legacy_terminology.py` (baselines orchestration.md and orchestration.yml). No CI freshness gate exists for contextive.
- **Inconsistencies:**
  - `historical-terms.md:17-18`
  - Lane Consolidation `orchestration.md:571`
  - the 7-lane list `orchestration.md:166`
  - conventions schema `glossary-conventions.md:46-53`
  - contextive slug table `contextive-glossaries.md:80-92` and `contextive-map.yaml:9/:13-16`
  - "inside a mission run": seed :598, pack :679, `execution.md:260`
  - the stale orchestration.yml
