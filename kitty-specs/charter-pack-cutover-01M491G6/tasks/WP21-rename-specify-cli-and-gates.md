---
work_package_id: WP21
title: Identifier rename R3/R4 — specify_cli, migrations, gates
dependencies:
- WP16
- WP20
requirement_refs:
- FR-010
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
subtasks:
- T098
- T099
- T100
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: lexical-larry
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_charter_pack_health.py
- src/specify_cli/cli/commands/charter/_fresh_project_layer.py
- src/specify_cli/charter_pack_synthesizer/
- tests/charter_pack_synthesizer/
- tests/architectural/test_charter_facades_reexport_offering.py
- tests/architectural/test_offering_missions_stale_path_sweep.py
- tests/architectural/test_charter_offering_public_surface.py
- tests/architectural/test_kernel_no_charter_offering_import.py
- tests/specify_cli/cli/commands/test_charter_pack_collect.py
- tests/specify_cli/cli/commands/test_charter_pack_hard_fail_surfacing.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_doctrine_health.py
- src/specify_cli/cli/commands/_charter_pack_health.py
- src/specify_cli/cli/commands/_profile_health_render.py
- src/specify_cli/cli/commands/charter/_fresh_project_layer.py
- src/specify_cli/cli/commands/charter/__init__.py
- src/specify_cli/cli/commands/charter/_cascade_shared.py
- src/specify_cli/cli/commands/agent_retrospect.py
- src/specify_cli/*_service_factory.py
- src/specify_cli/doctrine_synthesizer/__init__.py
- src/specify_cli/doctrine_synthesizer/conflict.py
- src/specify_cli/doctrine_synthesizer/provenance.py
- src/specify_cli/charter_pack_synthesizer/**
- src/specify_cli/charter_runtime/freshness/cache.py
- src/specify_cli/invocation/registry.py
- src/specify_cli/invocation/org_profiles.py
- src/specify_cli/skills/registry.py
- src/specify_cli/template/manager.py
- src/specify_cli/migration/rewrite_shims.py
- src/specify_cli/tool_surface/profiles/projection.py
- src/specify_cli/.contextive/governance.yml
- src/specify_cli/upgrade/migrations/m_2_1_2_fix_orchestrator_api_skill.py
- src/specify_cli/upgrade/migrations/m_2_1_2_fix_runtime_next_skill.py
- src/specify_cli/upgrade/migrations/m_2_1_2_install_git_workflow_skill.py
- src/specify_cli/upgrade/migrations/m_2_1_2_install_mission_system_skill.py
- src/specify_cli/upgrade/migrations/m_2_1_3_restore_prompt_commands.py
- src/specify_cli/upgrade/migrations/m_2_1_4_enforce_command_file_state.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc30_fix_runtime_next_result_default.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_fix_prompt_file_workaround.py
- tests/architectural/_dead_path_scan.py
- tests/architectural/_inert_slots.py
- tests/architectural/test_charter_facades_reexport_offering.py
- tests/architectural/test_charter_sole_door_*_service.py
- tests/architectural/test_doctrine_missions_stale_path_sweep.py
- tests/architectural/test_offering_missions_stale_path_sweep.py
- tests/architectural/test_charter_offering_public_surface.py
- tests/architectural/test_kernel_no_doctrine_import.py
- tests/architectural/test_kernel_no_charter_offering_import.py
- tests/architectural/test_kernel_env_expand_no_upward_import.py
- tests/architectural/test_bridge_cores_import_boundary.py
- tests/architectural/test_clock_import_ban.py
- tests/architectural/test_ratchet_positional_anchor_ban.py
- tests/_support/wall_clock_assertions.py
- tests/architectural/test_glossary_authority_parity.py
- tests/architectural/test_glossary_pack_parity.py
- tests/architectural/test_issue_matrix_json_migration_completeness.py
- tests/architectural/test_issue_matrix_partition_guard.py
- tests/architectural/test_no_authored_applies_edge.py
- tests/architectural/test_no_shipped_layer_label.py
- tests/architectural/test_override_policy_parity.py
- tests/architectural/test_ratchet_baselines.py
- tests/architectural/test_no_dead_doctrine_paths.py
- tests/specify_cli/cli/commands/test_charter_pack_collect.py
- tests/specify_cli/cli/commands/test_doctrine_hard_fail_surfacing.py
- tests/specify_cli/cli/commands/test_charter_pack_hard_fail_surfacing.py
- tests/specify_cli/test_*_service_factory.py
- tests/doctrine_synthesizer/__init__.py
- tests/doctrine_synthesizer/test_conflict_failclosed.py
- tests/doctrine_synthesizer/test_provenance.py
- tests/charter_pack_synthesizer/**
- tests/specify_cli/charter/test_graph_unlink_helper.py
- tests/specify_cli/test_read_seam_migration_core.py
- tests/integration/test_implement_review_retrospect_smoke.py
- tests/integration/retrospective/test_next_mission_sees_change.py
- tests/cli/test_agent_retrospect_missing_record.py
- tests/cli/test_agent_retrospect_synthesize.py
- tests/cli/commands/test_retrospect.py
- tests/retrospective/test_reducer_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP21 – Identifier rename R3/R4 — specify_cli, migrations, gates

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `lexical-larry`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(If WP18 has already retired `ad-hoc-profile-load`, use its replacement `spk-charter-profile-load`.)

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Finish the FR-010 identifier rename for the last two slices of `research/package-split-and-paths.md` Part C:

- **R3**: identifiers and module names *defined in* `src/specify_cli/` that carry the retired-tier "doctrine" sense (the offer-side tier, the project layer, the `doctor doctrine` health report, the retrospective applier that writes the project layer).
- **R4**: identifiers in the older migration bodies, the synthesizer applier package, `doctrine_service_factory`, and the architectural gates.

Done when:

1. Re-running the token scan (Step 0 of T098) over `src/specify_cli/` and `tests/architectural/` lists only (a) content-sense names you kept on purpose and recorded, (b) names the spec keeps (NFR-002 gate file names, migration ids, C-004), (c) residue owned by a later WP and recorded with that WP's id.
2. Every `pending_until("WP21")` strict-xfail in `tests/acceptance/charter_pack_cutover/` is removed and green.
3. No re-export alias, no `doctrine_*` module left as a forwarding stub, no `import x as doctrine_x` (C-001).
4. `make test-fast`, the touched-module tests, the named gate files, `mypy --strict` on touched sources and the ruff checks are green.

## Context & Constraints

Read before starting:

- `kitty-specs/charter-pack-cutover-01M491G6/spec.md` (FR-010, NFR-002, C-001, C-002, C-004, occurrence map rules).
- `kitty-specs/charter-pack-cutover-01M491G6/research/package-split-and-paths.md` §C (sizing, R3/R4 scope) and §A.4 (rosters).
- `kitty-specs/charter-pack-cutover-01M491G6/occurrence_map.yaml`: `code_symbols` / `import_paths` / `tests_fixtures` are `rename`; `user_facing_strings` is `manual_review`; `migration_id` fields and `src/specify_cli/upgrade/metadata.py` are `do_not_change`; historical mission slugs in comments are `do_not_change`.
- `.kittify/charter/charter.md` and `spec-kitty charter context --action implement`.
- The Activity Logs of WP19 and WP20: they fixed the new names for `DoctrineService`, `build_activation_aware_doctrine_service`, `doctrine_root` (built-in root parameter), `resolve_doctrine_root`, `doctrine_service_builder` and `DoctrineSelectionConfig`. **Match their nouns.** By the time WP21 starts, their call sites in `specify_cli` are already renamed; WP21 renames only what `specify_cli`, the migrations and the gates *define*.

Key rules:

- **"doctrine" by sense.** Rename the retired-tier sense. Keep the content sense ("doctrine" as governance substance), C-004 names (`doctrine-daphne`, `DIRECTIVE_039`), and historical mission slugs in comments. Examples measured at base:
  - rename: `DoctrineHealthReport` (health of charter packs), `_doctrine_collect`, `_fresh_doctrine` (it materialises the project layer), `doctrine_synthesizer` (writes the project layer), `doctrine_data_root = files("charter.offering")` (the offering root), `doctrine_dirty` (dirty paths under the project layer), `_DOCTRINE_ROUTING_LAYERS` (offering layers).
  - keep, and record: `retrospective/policy.py` `propose_doctrine_changes` (a persisted policy key, content sense, not in the FR-012 inventory); class names `FixCharterDoctrineSkillMigration` and `RetireSingleOwnerDoctrineIdsMigration` and every migration module file name (they mirror recorded `migration_id` values); the NFR-002 gate file names `test_doctrine_census.py`, `test_lifted_cli_doctrine_retirement.py`, `test_no_deprecated_doctrine_command_in_guidance.py`, `test_no_dead_doctrine_paths.py`.
- **C-001**: rename in place with `git mv`; update every importer; leave no forwarding module, no alias in `__all__`, no `X = Y` alias.
- **Ownership**: files moved or deleted by WP04/WP05/WP13/WP16 are gone. Files named for another WP's subtask (for example `cli/commands/doctor.py` for WP15, `charter/generate.py` and `init.py` for WP09, `charter/activate.py` and `pack.py` for WP08/WP13, `interview.py` and `_resynthesis_preflight.py` for WP06, `tracker.py` for WP14, the `ToolSurfaceKind` files for WP17, `m_unify_charter_activation.py` and `m_2_1_2_fix_glossary_context_skill.py` for WP06/WP10, `test_doctrine_census.py` and `test_runtime_charter_doctrine_boundary.py` for WP05) are **not** in `owned_files`. When a rename here needs a call-site edit in one of them, make it as a mechanical follow-up (tasks.md rule) and log each file with a one-line rationale. Shared rosters (`pyproject.toml`, `ruff.toml`, `.github/ci-module-registry.yml`, `.github/ci-shard-timings.json`, `.github/workflows/ci-router.yml`, `.github/workflows/ci-nightly.yml`, `tests/architectural/_gate_coverage.py`, `tests/architectural/_interpreter_shard_roster.py`, `tests/architectural/ci_topology_census.json`, `tests/release/coverage_breadth_baseline.json`, `tests/release/ci_retirement_scrub.json`) are edited the same way and logged.
- **Sources owned upstream, destinations owned here.** These files are claimed by earlier WPs and are renamed, moved or edited here as logged follow-ups (their WPs are complete before WP21 starts): WP02 `src/specify_cli/cli/commands/_doctrine_collect.py`, `charter/_status_collectors.py`, `profiles_cmd.py`, `charter_runtime/preflight/runner.py`; WP03 `charter/_fresh_doctrine.py`, `charter/_synthesis.py`, `charter/synthesize.py`, `doctrine_synthesizer/apply.py`, `charter_runtime/freshness/computer.py`, `tests/doctrine_synthesizer/test_apply.py`, `tests/doctrine_synthesizer/test_path_traversal_rejection.py`; WP04 `tests/architectural/test_charter_facades_reexport_doctrine.py`, `test_doctrine_public_surface.py`; WP05 `charter_runtime/lint/checks/org_layer.py`, `tests/specify_cli/cli/commands/test_doctrine_collect.py`; WP17 `charter/deactivate.py`; WP19 `tests/architectural/_sole_door_scan.py`; WP20 `tests/architectural/test_charter_sole_door_inner_reacharound.py`, `test_no_op_stable_writes.py`, `tests/specify_cli/invocation/test_org_profiles.py`. The move destinations (`_charter_pack_collect.py`, `_fresh_project_layer.py`, `charter_pack_synthesizer/**`, `tests/charter_pack_synthesizer/**`, the renamed gate and test files) are owned here.
- **Downstream docs**: do not edit living docs (WP22 owns them). Record every doc that still names a renamed module or gate file (for example `docs/development/reference/ci-gate-mechanics.md` names `test_charter_facades_reexport_doctrine`) in the Activity Log so WP22 sweeps it.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes must merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- **Lane**: from `lanes.json` (filled by finalize).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Never push to `main`. Commit often, conventional subjects referencing #3732, for example `refactor(cli): rename doctor health report to CharterPackHealthReport (#3732)`.

## Subtasks & Detailed Guidance

### Red first (C-006 / C-011) — first commit

1. `grep -rn 'pending_until("WP21")' tests/acceptance/charter_pack_cutover/`. WP01's flip map assigns WP21 `test_fr010_retired_identifiers_absent[r3r4]` (an AST/token scan of `src/specify_cli/**` for the closed R3/R4 list in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml`, for example `OrgDoctrineSource`, `doctrine_service_factory`, `doctrine_synthesizer`) and `test_fr010_no_src_module_named_for_retired_tier` in `test_package_split.py`: no `src/**` path segment contains `doctrine` except the kept migration ids in the occurrence map. At base the offending paths outside WP21's scope were `src/kernel/doctrine_root.py` (WP02), `src/charter/activation/{_doctrine_paths,action_doctrine_bundle,doctrine_service_builder}.py` (WP20), `src/charter/offering/skills/spk-doctrine-*` and `spec-kitty-charter-doctrine` (WP18), `src/specify_cli/doctrine/` (WP05), `cli/commands/doctrine.py` (WP16), `_doctrine_asset.py` (WP15 moves it to `charter/pack_asset.py`). If any of them still exists when you start, it is that WP's miss: record it and raise it with the reviewer before renaming it yourself. The two kept migration modules (`m_2_1_2_fix_charter_doctrine_skill.py`, `m_4_0_0rc5_retire_single_owner_doctrine_ids.py`) must be in the test's exception set; if they are not, raise it (C-006: do not edit the test).
2. Remove each marker (the decorator only; do not change the assertion). Run them: they must fail on the current tree. Paste the failing test ids and the red summary line into the Activity Log.
3. Commit: `test(acceptance): drop WP21 xfail markers for FR-010 R3/R4 (#3732)`.
4. If a WP21 test passes immediately, stop: it is vacuous or already satisfied by WP19/WP20. Record which, and ask the reviewer before changing it (C-006 forbids redefining acceptance criteria).

### Subtask T098 – R3 rename: `specify_cli` command modules and neighbours

- **Purpose**: the CLI layer stops naming the retired tier in its own identifiers and module names.
- **Steps**:
  0. **Measure.** Re-run the token scan from research §C on the live tree (identifiers only, via `tokenize`; strings and comments excluded):
     ```bash
     uv run --frozen python -I - <<'EOF'
     import io, pathlib, re, tokenize, collections, sys
     for root in ("src/specify_cli", "tests/architectural"):
         for p in sorted(pathlib.Path(root).rglob("*.py")):
             if "__pycache__" in p.parts: continue
             toks = tokenize.generate_tokens(io.StringIO(p.read_text()).readline)
             c = collections.Counter(t.string for t in toks if t.type == tokenize.NAME and re.search("doctrine", t.string, re.I))
             if c: print(p, dict(c))
     EOF
     ```
     Save the output to the Activity Log (counts only). At base it listed about 60 `src/specify_cli` files; after WP04/WP05/WP16/WP19/WP20 most remaining hits are names defined in `specify_cli`.
  1. **Module moves** (`git mv`, then fix importers with `git grep -l`):
     - `cli/commands/_doctrine_collect.py` → `cli/commands/_charter_pack_collect.py`. Inside: `project_doctrine` locals → `project_layer`; helper names that say "doctrine" for the pack tier get the charter-pack noun. Importers at base: `cli/commands/doctor.py` (WP15-owned, follow-up), `_profile_health_render.py`, `charter_runtime/lint/checks/org_layer.py`, `charter/__init__.py`; charter-side docstrings `charter/activation/action_grain.py`, `synthesizer/graph_residue.py`, `offering/drg/override_policy.py` (WP19/WP20-owned, follow-up).
     - `cli/commands/_doctrine_health.py` → `cli/commands/_charter_pack_health.py`; `DoctrineHealthReport` → `CharterPackHealthReport`. The JSON shape from `to_dict()` is unchanged (spec FR-006: `doctor charter-packs` JSON keys unchanged); `tests/cli/test_doctor_doctrine_selections_snapshot.py` must stay byte-identical in its expected output.
     - `cli/commands/charter/_fresh_doctrine.py` → `cli/commands/charter/_fresh_project_layer.py`; `_materialize_fresh_doctrine` → `_materialize_fresh_project_layer`, `_planned_fresh_doctrine_paths`/`_deletes` → `_planned_fresh_project_layer_paths`/`_deletes`, `_MINIMAL_FRESH_DOCTRINE_PROVENANCE_TEMPLATE` → `_MINIMAL_FRESH_PROJECT_LAYER_PROVENANCE_TEMPLATE`, `_synthesize_project_doctrine` → `_synthesize_project_layer`, `doctrine_dir` → `project_pack_dir`. Update `charter/__init__.py` (imports and `__all__`), `charter/_synthesis.py`, `charter/synthesize.py`.
     - `doctrine_service_factory.py` → `<noun>_service_factory.py`, where `<noun>` follows WP20's rename of `build_activation_aware_doctrine_service` (if WP20 chose `build_activation_aware_charter_service`, the module is `charter_service_factory.py`). Update `invocation/org_profiles.py`, `invocation/registry.py`, `cli/commands/profiles_cmd.py`, `.contextive/governance.yml` (definition text), the charter-side docstrings, and `tests/architectural/test_charter_sole_door_inner_reacharound.py` `_FACTORY_MODULES` (line ~108) plus its planted source strings (~410, ~459).
  2. **Renderer names** in `_profile_health_render.py`: `_render_doctrine_pack` → `_render_charter_pack`, `_emit_doctrine_json`/`_human`/`_no_packs` → `_emit_charter_packs_json`/`_human`/`_no_packs`. If WP15 already renamed them while moving `doctor doctrine` to `doctor charter-packs`, keep WP15's names.
  3. **Neighbours** (identifiers only):
     - `charter_runtime/freshness/computer.py` `_doctrine_graph_path`, `_doctrine_dir` → `_project_pack_graph_path`, `_project_pack_dir`; `freshness/cache.py` caller.
     - `charter_runtime/preflight/runner.py` `doctrine_dirty` → `project_pack_dirty` (~787-795).
     - `charter_runtime/lint/checks/org_layer.py` `_build_doctrine_service` import alias → WP20's noun.
     - `invocation/registry.py` `_DOCTRINE_ROUTING_LAYERS` (line 29) → `_OFFERING_ROUTING_LAYERS`.
     - `skills/registry.py` `doctrine_root` (~91) and `template/manager.py` `doctrine_data_root` (~220-225) → `offering_root` / `offering_data_root`.
     - `migration/rewrite_shims.py` `doctrine_steps` (~56) → `offering_steps`.
     - `charter_packs/sources/protocol.py` (moved by WP05) `OrgDoctrineSource` → `OrgCharterPackSource` (owner-veto name, orchestrator ruling FI-S7), with its implementers, the `charter_packs/__init__.py` docstring and the docstring mentions in `review/scope_source.py`.
     - `tool_surface/profiles/projection.py` `_build_activation_aware_doctrine_service` import alias → WP20's noun.
     - `charter/_cascade_shared.py`, `charter/deactivate.py`, `charter/_status_collectors.py`: `doctrine_root` parameters and locals → the name WP19 gave the built-in root parameter.
     - `profiles_cmd.py` `doctrine_repo`, `project_doctrine_profiles` → `offering_repo`, `project_layer_profiles`.
     - `charter/_synthesis.py` `doctrine_snapshot` / `doctrine_kind_subdir`: if these are charter-defined names, WP20 already renamed them; only local residue is yours.
  4. **Follow-up call sites** in files you do not own: `cli/commands/charter/generate.py` defines `_build_doctrine_service_with_org_layer` (re-exported from `charter/__init__.py`, used by `activate.py`, `pack.py`): rename to WP20's noun (`_build_<noun>_service_with_org_layer`) everywhere; log each file.
  5. Re-run the Step 0 scan. Classify every remaining hit in the Activity Log: kept (reason), out of scope (owner WP), or missed (fix it).
- **Files**: the R3 entries in `owned_files`; follow-ups logged.
- **Parallel?**: No; T099 and T100 depend on the new names.
- **Notes**:
  - Do not rename user-facing strings here except where a string is a module path (patch targets such as `"specify_cli.cli.commands._doctrine_collect.load_built_in_graph"` in tests). Prose belongs to WP22.
  - `mypy` sees `specify_cli.*` with `follow_imports = "skip"`; a stale import will not fail mypy. Rely on the tests and on `python -c "import specify_cli.cli.commands._charter_pack_collect"`.
  - Check `src/specify_cli/_completion_manifest.json` freshness (`tests/architectural/test_completion_manifest_freshness.py`); module renames normally do not change it, regenerate with `uv run --frozen python -m specify_cli.completion --regenerate` only if the gate says so.
- **Validation**:
  - [ ] Step 0 scan output classified in the Activity Log.
  - [ ] `git grep -n "_doctrine_collect\|_doctrine_health\|_fresh_doctrine\|doctrine_service_factory\|DoctrineHealthReport" -- src tests` returns nothing except historical records.
  - [ ] No forwarding module or alias left behind.

### Subtask T099 – R4 rename: migrations bodies, synthesizer applier, gates

- **Purpose**: the remaining non-historical identifiers in migrations, the retrospective applier and the architectural gates use the charter vocabulary.
- **Steps**:
  1. **Synthesizer applier package**: `git mv src/specify_cli/doctrine_synthesizer src/specify_cli/charter_pack_synthesizer` (it applies retrospective proposals into the project layer, `.kittify/charter-packs/`). Update its `__init__.py` docstring and imports, `apply.py` (`_DOCTRINE_BASE` → `_PROJECT_PACK_BASE`, `doctrine_dir` → `project_pack_dir`; WP03 already repointed the path to the kernel constant), `cli/commands/agent_retrospect.py`. Shared rosters as logged follow-ups: `ruff.toml:52` and `:165`, `pyproject.toml` ruff format-exclude entries for `apply.py` and `conflict.py` (~584-585; prefer formatting the moved files and dropping the entries, a shrink under `test_ruff_format_exclude_ratchet.py`), `.github/workflows/ci-router.yml:203`, `.github/ci-module-registry.yml:271,296`, `.github/workflows/ci-nightly.yml:646`, `.github/ci-shard-timings.json`, `tests/architectural/_gate_coverage.py`, `_interpreter_shard_roster.py:216,245`, `ci_topology_census.json:317`, `tests/release/coverage_breadth_baseline.json` (keys `src/specify_cli/doctrine_synthesizer/*`, `doctrine_service_factory.py`), `tests/release/ci_retirement_scrub.json:188`. Keep the roster bijection gates green (`test_module_shard_registry.py`, `test_gate_selection_authority.py`, `test_ci_collection_completeness.py` if present; run whichever of them exist).
  2. **Migration bodies** (never change a `migration_id`, class name or module file name):
     - `m_2_1_2_fix_orchestrator_api_skill.py:56-64`, `m_2_1_2_fix_runtime_next_skill.py`, `m_2_1_2_install_git_workflow_skill.py`, `m_2_1_2_install_mission_system_skill.py`, `m_3_2_0rc30_fix_runtime_next_result_default.py:49-57`, `m_3_2_0rc35_fix_prompt_file_workaround.py`: `doctrine_root = files("charter.offering")` → `offering_root`. The `/ "doctrine" / "skills"` fallback beside it points at the deleted `src/doctrine/`; if WP03 left it (FR-016 gate by-file exemption), delete the dead fallback only when the migration's own tests still pass, otherwise keep it and record why.
     - `m_2_1_3_restore_prompt_commands.py:96-140`, `m_2_1_4_enforce_command_file_state.py`: `doctrine_steps`, `doctrine_path` → `offering_steps`, `prompt_path`.
     - Verify the recorded ids are untouched: `git diff <base>..HEAD -- src/specify_cli/upgrade/migrations | grep -n "migration_id"` must show no changed line.
  3. **Gates** (identifier renames; file renames only where listed):
     - File renames with `git mv`: `test_charter_facades_reexport_doctrine.py` → `test_charter_facades_reexport_offering.py`; `test_doctrine_missions_stale_path_sweep.py` → `test_offering_missions_stale_path_sweep.py`; `test_doctrine_public_surface.py` → `test_charter_offering_public_surface.py`; `test_kernel_no_doctrine_import.py` → `test_kernel_no_charter_offering_import.py`; `test_charter_sole_door_doctrine_service.py` → `test_charter_sole_door_<WP19 service noun>_service.py`. Update every reference by name: `pyproject.toml` ruff exclude (~875, ~883, ~884), `.github/ci-shard-timings.json`, `tests/_support/wall_clock_assertions.py`, `test_bridge_cores_import_boundary.py`, `test_clock_import_ban.py`, `test_ratchet_positional_anchor_ban.py`, `test_kernel_env_expand_no_upward_import.py`, and docstrings in `src/charter/{assets,glossary_packs,missions,drg}.py`, `src/charter/offering/api.py` (WP19-owned, follow-up). Do not rename the four NFR-002-named files.
     - Identifier renames inside: `_dead_path_scan.py:39` and `test_no_authored_applies_edge.py:25` `_DOCTRINE_ROOT` → `_OFFERING_ROOT` / `_BUILT_IN_PACK_ROOT` (by what each points at); `_sole_door_scan.py` `DOCTRINE_LAYER_PREFIX`; `_inert_slots.py` `_NON_DOCTRINE_SCHEMAS`; `test_charter_sole_door_*_service.py` `RAW_/WRAPPER_DOCTRINE_SERVICE_QUALNAME`, `DOCTRINE_SERVICE_CANDIDATE_NAMES`, `DOCTRINE_SERVICE_TARGETS` (values follow WP19/WP20's class names); `test_issue_matrix_partition_guard.py` `scan_doctrine`, `GATE4_DOCTRINE`; `test_override_policy_parity.py` `_doctrine_collect`; `test_no_op_stable_writes.py` `doctrine_snapshot`; `test_no_shipped_layer_label.py`, `test_ratchet_baselines.py`, `test_issue_matrix_json_migration_completeness.py`, `test_glossary_pack_parity.py`, `test_glossary_authority_parity.py` (`_DOCTRINE_MD_PATH` names a file that no longer exists; keep the absence assertion, rename the constant to `_RETIRED_GLOSSARY_MD_PATH`), `test_no_dead_doctrine_paths.py` (`scan_doctrine_cross_links*`, `_DOCTRINE_ROOT`; keep the file name).
     - Gates owned upstream (`test_runtime_charter_doctrine_boundary.py` `_LazyDoctrineVisitor` and friends, `test_doctrine_census.py` `reached_doctrine_paths`, `test_kind_table_derivation.py`, `test_charter_sole_door_agent_profile_repository.py`, `test_charter_sole_door_resolver_imports.py`, `test_docs_cli_reference_parity.py`, `test_no_config_key_spelled_as_module_path.py`): rename residual identifiers as logged follow-ups. Test function names that assert a *removed* surface (for example `test_doctrine_curate_is_unknown_command`) keep "doctrine": they name the retired command on purpose.
- **Files**: R4 entries in `owned_files`; rosters as logged follow-ups.
- **Parallel?**: Migrations (step 2) and gates (step 3) can run in parallel after step 1.
- **Notes**: a gate whose identifiers change must still find what it found before. For each renamed gate, compare its collected test count before and after (`pytest --collect-only -q <file> | tail -1`) and record both numbers.
- **Validation**:
  - [ ] No `migration_id` changed.
  - [ ] Renamed gates collect the same number of tests and pass.
  - [ ] Roster bijection gates green.

### Subtask T100 – R3/R4 tests and pyproject entries

- **Purpose**: tests follow the code; nothing imports a removed module path.
- **Steps**:
  1. `git mv tests/doctrine_synthesizer tests/charter_pack_synthesizer`; update imports in its five files.
  2. `git mv tests/specify_cli/cli/commands/test_doctrine_collect.py .../test_charter_pack_collect.py`; `test_doctrine_hard_fail_surfacing.py` → `test_charter_pack_hard_fail_surfacing.py` (its docstring cites `DoctrineHealthReport`); `tests/specify_cli/test_doctrine_service_factory.py` → `test_<noun>_service_factory.py`. Update `pyproject.toml` entries that name them (ruff exclude, `test_doctrine_hard_fail_surfacing` reference) and `ci-nightly.yml` / `_interpreter_shard_roster.py` entries for the factory test.
  3. Update imports and patch-target strings in: `tests/specify_cli/charter/test_graph_unlink_helper.py`, `tests/specify_cli/test_read_seam_migration_core.py` (~118-293), `tests/integration/test_implement_review_retrospect_smoke.py`, `tests/integration/retrospective/test_next_mission_sees_change.py`, `tests/cli/test_agent_retrospect_missing_record.py`, `tests/cli/test_agent_retrospect_synthesize.py`, `tests/cli/commands/test_retrospect.py`, `tests/retrospective/test_reducer_integration.py`, `tests/specify_cli/invocation/test_org_profiles.py`.
  4. Follow-up edits (logged) in tests owned elsewhere that import the renamed modules: `tests/specify_cli/cli/commands/test_doctor_operating_procedures.py`, `test_doctor_override_diagnostics.py`, `test_doctor_doctrine_org_layer.py`, `tests/specify_cli/test_doctor_doctrine.py`, `tests/charter/test_doctrine_service_builder_unification.py`, and the `tests/doctrine/**` files that import them (`agent_profiles/test_drupal_dries_profile.py`, `drg/test_org_drg_bridge.py`, `drg/test_org_pack_node_inference.py`, `pack_skills/test_health.py`, `test_charter_profile_absorption.py`, `test_counts_derivation.py`, `test_doctrine_health_glossary_pack.py`, `test_pack_version_relocation.py`). Do not rename files under `tests/doctrine/` (WP23 moves that directory).
  5. `git grep -n "doctrine_synthesizer\|doctrine_service_factory\|_doctrine_collect\|_doctrine_health\|_fresh_doctrine" -- tests src .github pyproject.toml ruff.toml` must be empty apart from historical records.
- **Files**: T100 entries in `owned_files`; follow-ups logged.
- **Parallel?**: After T098/T099.
- **Notes**: a renamed test file keeps every test function; do not drop or merge tests. If `tests/architectural/test_timing_coverage_invariant.py` or `test_ci_corpus_trigger_completeness.py` name a moved path, update them as follow-ups.
- **Validation**:
  - [ ] Collection counts per moved test file unchanged.
  - [ ] Flipped WP21 acceptance tests green.

## Test Strategy

Run before every push and record commands with pass/fail counts in the Activity Log:

```bash
make test-fast
uv run --frozen pytest <every acceptance test id you un-xfailed> -q   # from the red-first grep
uv run --frozen pytest tests/charter_pack_synthesizer tests/specify_cli/cli/commands tests/specify_cli/charter \
  tests/specify_cli/test_read_seam_migration_core.py tests/specify_cli/invocation tests/cli/test_agent_retrospect_missing_record.py \
  tests/cli/test_agent_retrospect_synthesize.py tests/cli/commands/test_retrospect.py tests/retrospective/test_reducer_integration.py \
  tests/integration/test_implement_review_retrospect_smoke.py tests/integration/retrospective/test_next_mission_sees_change.py \
  tests/specify_cli/test_doctor_doctrine.py tests/cli/test_doctor_doctrine_selections_snapshot.py \
  tests/specify_cli/upgrade tests/upgrade tests/specify_cli/migration -q
# Specific gate files (never bare tests/architectural/):
uv run --frozen pytest tests/architectural/test_charter_facades_reexport_offering.py \
  tests/architectural/test_offering_missions_stale_path_sweep.py tests/architectural/test_charter_offering_public_surface.py \
  tests/architectural/test_kernel_no_charter_offering_import.py tests/architectural/test_kernel_env_expand_no_upward_import.py \
  tests/architectural/test_charter_sole_door_*_service.py tests/architectural/test_charter_sole_door_inner_reacharound.py \
  tests/architectural/test_glossary_authority_parity.py tests/architectural/test_glossary_pack_parity.py \
  tests/architectural/test_issue_matrix_partition_guard.py tests/architectural/test_issue_matrix_json_migration_completeness.py \
  tests/architectural/test_no_authored_applies_edge.py tests/architectural/test_no_op_stable_writes.py \
  tests/architectural/test_no_shipped_layer_label.py tests/architectural/test_override_policy_parity.py \
  tests/architectural/test_ratchet_baselines.py tests/architectural/test_no_dead_doctrine_paths.py \
  tests/architectural/test_runtime_charter_doctrine_boundary.py tests/architectural/test_doctrine_census.py \
  tests/architectural/test_no_dead_modules.py tests/architectural/test_ruff_format_exclude_ratchet.py \
  tests/architectural/test_completion_manifest_freshness.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_no_legacy_terminology.py -q
# Roster bijection gates (run those that exist):
ls tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py tests/architectural/test_ci_collection_completeness.py 2>/dev/null | xargs -r uv run --frozen pytest -q
uv run --frozen mypy --strict <every touched src file>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
```

## Risks & Mitigations

- **A patch target string still names the old module**: `monkeypatch.setattr("specify_cli...._doctrine_collect.x", ...)` fails only at run time. Mitigation: the T100 step 5 grep over strings, not only imports.
- **Roster drift**: renamed test directories that are missing from one roster file break CI selection. Mitigation: edit all roster files in one commit and run the bijection gates.
- **Content sense renamed by accident**: a "doctrine" that means governance content becomes "charter pack". Mitigation: every kept or renamed borderline name is recorded with its sense.
- **Name mismatch with WP19/WP20**: two nouns for one concept. Mitigation: read their Activity Logs first; reuse their nouns.

## Review Guidance

- Confirm the WP21 acceptance tests were red after the first commit and are green at the end (red-on-base → green-on-final), and that their assertions are unchanged.
- Confirm no forwarding module, alias or re-export remains (`git grep -n "doctrine" -- src/specify_cli | grep -n "import .* as "`).
- Confirm no `migration_id`, migration class name or migration module file name changed.
- Spot-check the kept-name list for sense (content vs tier).
- Confirm every follow-up edit in a non-owned file is logged with a rationale, and every stale doc reference is listed for WP22.
- Confirm `mypy --strict`, ruff check and `ruff format --check --force-exclude` ran on the touched files.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

## Carry-over from WP20

- Step 0 (red at WP20's base, separate commit, red → green): `tests/architectural/...::test_no_dead_src_path_literals_in_live_docs` — live docs cite src paths renamed/moved by WP19/WP20 (e.g. `doctrine_service_builder.py`, `action_doctrine_bundle.py`, `_doctrine_paths.py`); repoint those literals (path literals only; broader prose stays WP22's).
- `specify_cli.doctrine_service_factory` now only re-exports `build_active_charter_service` — delete it and repoint importers (no alias).
- `_build_doctrine_service_with_org_layer` still used in `charter/generate.py`, `charter/activate.py`.
- `doctrine_root` locals in `pack_tooling.py` (value = built-in pack root → `pack_root`), `authoring.py`, `_status_collectors.py`, `init.py`, `skills/registry.py`; `_fresh_doctrine.py` / `_planned_fresh_doctrine_paths`.
- Naming convention established: `offering_root` when the value is `resolve_offering_root()` (the charter.offering package dir); `pack_root` when it is a pack root; `charter_service` for service locals.
- TOOLING CAUTION: `.github/CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; textual renames over `git ls-files .github` write through it. Exclude symlinks from bulk rewrites; CHANGELOG is WP24's.
