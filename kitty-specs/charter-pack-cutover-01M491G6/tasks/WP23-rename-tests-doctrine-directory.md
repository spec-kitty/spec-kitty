---
work_package_id: WP23
title: Rename `tests/doctrine/`
dependencies:
- WP18
- WP21
- WP22
requirement_refs:
- FR-010
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
subtasks:
- T105
- T106
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: lexical-larry
authoritative_surface: tests/charter_offering/
create_intent:
- tests/charter_offering/
execution_mode: code_change
owned_files:
- tests/doctrine/agent_profiles/**
- tests/doctrine/assets/**
- tests/doctrine/directives/**
- tests/doctrine/fixtures/**
- tests/doctrine/glossary_packs/**
- tests/doctrine/mission_step_contracts/**
- tests/doctrine/missions/**
- tests/doctrine/model_task_routing/**
- tests/doctrine/paradigms/**
- tests/doctrine/procedures/**
- tests/doctrine/shared/**
- tests/doctrine/styleguides/**
- tests/doctrine/tactics/**
- tests/doctrine/toolguides/**
- tests/doctrine/__init__.py
- tests/doctrine/_builtin_inventory.py
- tests/doctrine/_relationship_graph.py
- tests/doctrine/_single_owner_detectors.py
- tests/doctrine/conftest.py
- tests/doctrine/drg/test_builtin_graph_seam.py
- tests/doctrine/drg/test_c4_and_anti_pattern_topology.py
- tests/doctrine/drg/test_cross_grain_integrity.py
- tests/doctrine/drg/test_drupal_dries_lineage.py
- tests/doctrine/drg/test_extractor_asset.py
- tests/doctrine/drg/test_glossary_node_kind.py
- tests/doctrine/drg/test_graph_sharding_equality.py
- tests/doctrine/drg/test_instantiates_edges.py
- tests/doctrine/drg/test_kind_mapping_totality.py
- tests/doctrine/drg/test_loader_multifile.py
- tests/doctrine/drg/test_mission_type_nodes.py
- tests/doctrine/drg/test_model_strictness_roundtrip.py
- tests/doctrine/drg/test_models.py
- tests/doctrine/drg/test_nodekind_artifactkind.py
- tests/doctrine/drg/test_org_drg_bridge.py
- tests/doctrine/drg/test_org_governance_failloud.py
- tests/doctrine/drg/test_org_pack_auto_emit.py
- tests/doctrine/drg/test_org_pack_config_cr04_charter_packs.py
- tests/doctrine/drg/test_org_pack_config_resolve_existing_org_roots.py
- tests/doctrine/drg/test_org_pack_config_resolve_org_dirs.py
- tests/doctrine/drg/test_org_pack_merge.py
- tests/doctrine/drg/test_org_pack_node_inference.py
- tests/doctrine/drg/test_override_policy_pack_sanctions.py
- tests/doctrine/drg/test_override_policy_predicates.py
- tests/doctrine/drg/test_profile_suggests_delivery.py
- tests/doctrine/drg/test_reachability.py
- tests/doctrine/drg/test_recursion_parity_gate.py
- tests/doctrine/drg/test_regen_roundtrip.py
- tests/doctrine/drg/test_resolve_transitive_refs.py
- tests/doctrine/drg/test_sharded_layout.py
- tests/doctrine/drg/test_shipped_graph_valid.py
- tests/doctrine/drg/test_single_owner_edges.py
- tests/doctrine/drg/test_tension_arbiters.py
- tests/doctrine/drg/test_tiered_standards_non_orphan.py
- tests/doctrine/drg/test_unknown_kind_fails_loudly.py
- tests/doctrine/drg/test_validator.py
- tests/doctrine/drg/test_validator_profile_edges.py
- tests/doctrine/drg/test_validator_structured_detection.py
- tests/doctrine/pack_skills/__init__.py
- tests/doctrine/pack_skills/conftest.py
- tests/doctrine/pack_skills/test_health.py
- tests/doctrine/pack_skills/test_models.py
- tests/doctrine/pack_skills/test_org_drg_skill_nodes.py
- tests/doctrine/pack_skills/test_repository.py
- tests/doctrine/pack_skills/test_validation.py
- tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py
- tests/doctrine/test_activation_parity_guard.py
- tests/doctrine/test_agent_profile_model_field.py
- tests/doctrine/test_api_surface_import.py
- tests/doctrine/test_artifact_compliance.py
- tests/doctrine/test_artifact_kinds.py
- tests/doctrine/test_base_org_layer.py
- tests/doctrine/test_built_in_location_authority.py
- tests/doctrine/test_builtin_cli_command_references.py
- tests/doctrine/test_capabilities.py
- tests/doctrine/test_change_scope_review_single_owner.py
- tests/doctrine/test_charter_activatable_vocabulary.py
- tests/doctrine/test_codex_dispatch_flags.py
- tests/doctrine/test_common_docs_single_owner.py
- tests/doctrine/test_debugger_debbie_artifacts.py
- tests/doctrine/test_directive_consistency.py
- tests/doctrine/test_discovery_recursion.py
- tests/doctrine/test_doctrine_health_glossary_pack.py
- tests/doctrine/test_doctrine_validate_lang_guard.py
- tests/doctrine/test_documentation_iteration_modes.py
- tests/doctrine/test_drg_merge.py
- tests/doctrine/test_drg_relations.py
- tests/doctrine/test_enriched_directives.py
- tests/doctrine/test_generic_agent_profile.py
- tests/doctrine/test_generic_artifact_language_bias.py
- tests/doctrine/test_glossary_link_integrity.py
- tests/doctrine/test_glossary_pack_kind.py
- tests/doctrine/test_human_in_charge_profile.py
- tests/doctrine/test_inline_ref_rejection.py
- tests/doctrine/test_isolation.py
- tests/doctrine/test_language_independent_tactics_unscoped.py
- tests/doctrine/test_loader_fail_closed.py
- tests/doctrine/test_mattpocock_skill_doctrine.py
- tests/doctrine/test_mission_review_skill_gate3_floor.py
- tests/doctrine/test_mission_review_skill_gate4.py
- tests/doctrine/test_mission_type_governance_isolation.py
- tests/doctrine/test_missions_root_packs_env.py
- tests/doctrine/test_model_task_routing_evaluator.py
- tests/doctrine/test_model_task_routing_loader.py
- tests/doctrine/test_model_task_routing_parity.py
- tests/doctrine/test_nested_artifact_discovery.py
- tests/doctrine/test_org_pack_delegation.py
- tests/doctrine/test_org_pack_subdir.py
- tests/doctrine/test_overlay_precedence.py
- tests/doctrine/test_overlay_recursion_loader.py
- tests/doctrine/test_owner_delivery.py
- tests/doctrine/test_pack_relocation_doctor_gate.py
- tests/doctrine/test_pack_relocation_guard.py
- tests/doctrine/test_pack_relocation_preflight.py
- tests/doctrine/test_pack_root_resolver.py
- tests/doctrine/test_package_smoke.py
- tests/doctrine/test_packaging_parity.py
- tests/doctrine/test_parse_shipped_yaml.py
- tests/doctrine/test_paula_patterns_artifacts.py
- tests/doctrine/test_post_validate_success_hook.py
- tests/doctrine/test_procedure_consistency.py
- tests/doctrine/test_profile_diagnostics.py
- tests/doctrine/test_profile_inheritance.py
- tests/doctrine/test_profile_model.py
- tests/doctrine/test_profile_repository.py
- tests/doctrine/test_profile_schema_validation.py
- tests/doctrine/test_project_charter_single_owner.py
- tests/doctrine/test_provenance_normalizer.py
- tests/doctrine/test_relation_doc_parity.py
- tests/doctrine/test_relationship_fields_rejected.py
- tests/doctrine/test_relationship_migration.py
- tests/doctrine/test_resolver.py
- tests/doctrine/test_retired_ids_absent.py
- tests/doctrine/test_retirement_table_consistency.py
- tests/doctrine/test_retrospective_drg.py
- tests/doctrine/test_rework_guidance_unforced.py
- tests/doctrine/test_role_value_object.py
- tests/doctrine/test_schema_generation_integrity.py
- tests/doctrine/test_schema_utils.py
- tests/doctrine/test_schema_validation.py
- tests/doctrine/test_served_prompts_single_owner.py
- tests/doctrine/test_service.py
- tests/doctrine/test_service_org_layer.py
- tests/doctrine/test_shipped_profiles.py
- tests/doctrine/test_spdd_reasons_artifacts.py
- tests/doctrine/test_spdd_reasons_skill.py
- tests/doctrine/test_spec_kitty_skill_content.py
- tests/doctrine/test_spk_show_me_skill.py
- tests/doctrine/test_spk_skill_pack.py
- tests/doctrine/test_structure_templates.py
- tests/doctrine/test_supply_chain_security_layer.py
- tests/doctrine/test_supply_chain_single_owner.py
- tests/doctrine/test_tactic_compliance.py
- tests/doctrine/test_task_class_map.py
- tests/doctrine/test_task_class_map_catalog_contract.py
- tests/doctrine/test_template_discovery.py
- tests/doctrine/test_testing_doctrine_single_owner.py
- tests/doctrine/test_versioning.py
- tests/doctrine/test_wheel_packaging.py
- tests/doctrine/test_wp_authoring_contract_roundtrip.py
- tests/doctrine/drg/migration/**
- tests/doctrine/drg/reachability_fixtures/**
- tests/charter_offering/**
- tests/architectural/test_ci_corpus_trigger_completeness.py
- tests/architectural/test_timing_coverage_invariant.py
- tests/architectural/_inert_slots_baseline.yaml
- tests/ci/test_corpus_blocking_home.py
- tests/next/test_discovery_step_contract.py
- tests/fixtures/mission_type_canonical/README.md
- tests/kernel/test_env_expand.py
- tests/docs/test_module_readme_lint.py
- tests/cli/test_mission_agnostic_flag.py
- tests/runtime/next/test_composed_guard_launder.py
- tests/release/coverage_breadth_evidence.md
- tests/integration/test_org_pack_chain_delivery.py
- tests/integration/test_mission_type_resolution_integration.py
- docs/architecture/doctrine-relationships.md
- docs/architecture/04_implementation_mapping/README.md
- docs/operations/p0-baseline-refresh.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP23 – Rename `tests/doctrine/`

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `lexical-larry`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(WP18 retires `ad-hoc-profile-load`; use `spk-charter-profile-load` if the old name is gone.)

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

Move the test tree that covers `src/charter/offering/**` from `tests/doctrine/` to `tests/charter_offering/`, update every reference (AGENTS.md test policy, `pyproject.toml`, `ruff.toml`, CI workflows, the CI rosters, other tests, docs, source comments), and rename the residual tier-sense test identifiers inside it.

Done when:

1. `tests/doctrine/` does not exist; `tests/charter_offering/` holds every file it held (same count, 325 files at base including fixtures; re-count at start) and collects the same number of tests.
2. `git grep -n "tests/doctrine\b\|tests\.doctrine\b" -- . ':!kitty-specs' ':!docs/adr' ':!docs/plans' ':!docs/reports' ':!docs/archive' ':!docs/changelog' ':!.kittify/evidence' ':!.kittify/migrations' ':!kitty-ops' ':!research-outputs'` returns nothing (historical records keep the old path, C-002).
3. The CI routing still selects the moved tests for `src/charter/offering/**` changes (roster bijection gates green; the packs workflow path filter covers the new directory).
4. Every `pending_until("WP23")` strict-xfail in `tests/acceptance/charter_pack_cutover/` is removed and green.

## Context & Constraints

- Spec FR-010; plan "Structure Decision" (the directory rename is its own late, mechanical WP); research `package-split-and-paths.md` §C (193 files with identifier hits; `tests/doctrine/` is the second owning-subsystem directory for `src/charter/offering/**` in the CLAUDE.md test policy).
- CLAUDE.md is a symlink to `AGENTS.md`. **AGENTS.md is owned by WP22**, which runs before this WP (WP23 depends on WP22). Edit only the test-policy words naming `tests/doctrine/` (line ~265, "touching `src/charter/offering/**` ⇒ both `tests/charter/` and `tests/doctrine/` — the doctrine test tree did not move …") and log it as a follow-up edit in a WP22-owned file.
- Shared rosters are edited as logged follow-ups (tasks.md rule): `pyproject.toml` (about 142 lines naming `tests/doctrine/...`, mostly the `[tool.ruff.format].exclude` ratchet), `ruff.toml` (8), `.github/ci-module-registry.yml` (l.164, 199-207, 288), `.github/workflows/packs.yml` (l.6, 133, 284 `--deselect tests/doctrine/test_shipped_profiles.py::...`), `.github/workflows/ci-router.yml` (l.972), `.github/workflows/ci-nightly.yml` (l.710), `.github/ci-shard-timings.json`, `tests/architectural/_interpreter_shard_roster.py`, `tests/architectural/_gate_coverage.py` and `tests/architectural/ci_topology_census.json` if they key on the directory.
- Source comments that cite `tests/doctrine/...` live in files owned by WP19/WP20/WP21 and others (`src/charter/activation/context_renderers/delivery_table.py`, `src/charter/activation/synthesizer/project_drg.py`, `src/charter/offering/{artifact_kinds,discovery_recursion}.py`, `src/charter/offering/drg/{models,org_pack_config,query}.py`, `src/charter/offering/drg/migration/{extractor,hand_authored_overlay}.py`, `src/charter/offering/missions/{glossary_hook,mission_type_repository,mission_step_repository}.py`, `src/kernel/sibling_paths.py`, `src/specify_cli/cli/commands/charter/activate.py`, `src/specify_cli/dossier/manifest.py`, `src/specify_cli/invocation/task_class_map.py`, `src/specify_cli/upgrade/migrations/m_3_3_1_context_sources_consolidation.py`): mechanical follow-ups, logged.
- Tests outside the moved tree that cite it (`tests/charter/**`, `tests/specify_cli/**`) are mostly owned by upstream WPs; edit them as logged follow-ups. The files in `owned_files` are the ones no other WP claims.
- The four docs in `owned_files` also carry retired-tier prose. WP22 (upstream) does not own them, so apply WP22's prose rule there (rename the retired-tier sense, keep the content sense; see `tasks/WP22-prose-packs-and-docs.md`, "Classification rule"), and record each change.
- **Files under `tests/doctrine/` claimed by earlier WPs** move with the tree as logged follow-ups: WP04 `drg/test_org_fragment_validation.py`, `drg/test_sharding_silent_degrade.py`, `test_builtin_manifest.py`, `test_charter_profile_absorption.py`, `test_counts_derivation.py`, `test_org_pack_augmentation.py`, `test_pack_id_identity.py`, `test_pack_lineage.py`, `test_pack_manifest_schema.py`, `test_pack_version_relocation.py`, `test_template_asset_e2e.py`; WP05 `pack_skills/test_kind_registration.py`; WP06 `test_activation_squad_lenses.py`, `test_squad_procedure_single_owner.py`; plus any file an earlier WP added to the tree after planning. `tests/dossier/test_manifest.py` is WP20's. Everything else in the tree is listed in `owned_files`; the destination `tests/charter_offering/**` is owned here.
- Historical roots keep `tests/doctrine` (C-002): `kitty-specs/`, `docs/adr/`, `docs/plans/`, `docs/reports/`, `docs/archive/`, released changelog sections and `docs/changelog/2x/**`, `.kittify/evidence/`, `.kittify/migrations/`, `kitty-ops/`, `research-outputs/`, and `tests/docs/fixtures/changelog_unreleased_pre_rewrite.md` (a frozen fixture). `docs/context/charter.md` (WP24) and `docs/migrations/relocate-builtin-doctrine-packs.md` (WP24, historical banner) are not yours; list them in the Activity Log for WP24/WP25.
- C-001: no `tests/doctrine` symlink, no re-export `conftest.py`, no `tests/doctrine/__init__.py` stub.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `issue-3732-charter-pack-rename`; completed changes must merge back into `issue-3732-charter-pack-rename`.
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`
- **Lane**: from `lanes.json` (filled by finalize).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Never push to `main`. The directory move and every roster edit go in **one commit** (the rosters are cross-checked), for example `test: rename tests/doctrine to tests/charter_offering (#3732)`; identifier renames in a second commit.

## Subtasks & Detailed Guidance

### Red first (C-006 / C-011) — first commit

1. `grep -rn 'pending_until("WP23")' tests/acceptance/charter_pack_cutover/`: WP01 assigns WP23 `test_fr010_tests_doctrine_directory_renamed` in `test_package_split.py`.
2. Remove the markers only; run them; record the red output; commit `test(acceptance): drop WP23 xfail markers (#3732)`.
3. A test that passes immediately is vacuous: record it and ask the reviewer.

### Subtask T105 – `tests/doctrine/` → `tests/charter_offering/`; references

- **Purpose**: the offering's test tree carries the offering's name; CLAUDE.md's owning-subsystem rule names it.
- **Steps**:
  1. Baseline: `find tests/doctrine -type f -not -path '*/__pycache__/*' | wc -l` and `uv run --frozen pytest tests/doctrine --collect-only -q | tail -1`. Record both.
  2. `git mv tests/doctrine tests/charter_offering`. Confirm `tests/charter_offering` did not exist before (it did not at base).
  3. Dotted imports: `git grep -n "tests\.doctrine" -- src tests` (at base: about 30 inside the tree, `tests/next/test_discovery_step_contract.py:47`, a docstring in `src/charter/offering/missions/mission_step_repository.py:210`). Replace with `tests.charter_offering`.
  4. Path strings: `git grep -n "tests/doctrine" -- . ':!kitty-specs' ':!docs/adr' ':!docs/plans' ':!docs/reports' ':!docs/archive' ':!.kittify/evidence' ':!.kittify/migrations'`. At base the counts were: `pyproject.toml` 142, `tests/architectural/test_ci_corpus_trigger_completeness.py` 73, `ruff.toml` 8, `src/charter/offering/drg/migration/extractor.py` 6, `docs/architecture/doctrine-relationships.md` 6, `docs/architecture/04_implementation_mapping/README.md` 5, `docs/operations/p0-baseline-refresh.md` 4, `.github/ci-module-registry.yml` 4, `.github/ci-shard-timings.json` 4, `.github/workflows/packs.yml` 3, then about 45 files with one to four each. Rewrite each to `tests/charter_offering`.
  5. `pyproject.toml` ruff format-exclude: the list is sorted and ratcheted (`tests/architectural/test_ruff_format_exclude_ratchet.py`, `test_every_exclude_entry_exists_on_disk`). Renamed entries must move to their sorted position; the count must not grow. Formatting a moved file and dropping its entry is allowed (a shrink).
  6. CI rosters (one commit with the move): `.github/ci-module-registry.yml`, `.github/workflows/{packs,ci-router,ci-nightly}.yml`, `.github/ci-shard-timings.json`, `tests/architectural/_interpreter_shard_roster.py`, `tests/architectural/_gate_coverage.py`, `tests/architectural/ci_topology_census.json`. The packs workflow's path filter (`packs.yml:133`) and the "exclude `tests/doctrine/**` from every code shard" split it describes (l.6) must name the new directory, or the moved tests stop running anywhere.
  7. AGENTS.md test policy (see Context), and any other living doc that tells contributors to run `tests/doctrine/` (`git grep -n "tests/doctrine" -- docs/development docs/guides` after the sweep).
  8. Re-run the baseline commands on `tests/charter_offering`; both numbers must match step 1.
- **Files**: `tests/doctrine/**` → `tests/charter_offering/**`, owned reference files, logged follow-ups.
- **Parallel?**: No.
- **Notes**:
  - `tests/charter_offering/conftest.py` and `__init__.py` move with the tree; check for `Path(__file__).parents[N]` arithmetic that assumed the old depth (same depth, so it should hold; verify the fixtures load).
  - `test_ci_corpus_trigger_completeness.py` enumerates corpus paths: update its expectations, do not loosen them.
  - `tests/architectural/test_timing_coverage_invariant.py:197` keys a file by path; WP21 may have renamed that file inside the tree. Use the final path.
  - The `.kittify/test-suite-speedup-workflow.js` script names the directory; `.kittify/` is outside FR-018 but it is a live tool; update it as a logged follow-up if it is tracked and used, otherwise record why not.
- **Validation**:
  - [ ] File count and collected-test count unchanged.
  - [ ] The step 4 grep returns only historical roots.
  - [ ] Roster bijection gates green.

### Subtask T106 – Residual test identifiers

- **Purpose**: test names in the moved tree follow the code renames of WP19–WP21; tier-sense names go, content-sense and C-004 names stay.
- **Steps**:
  1. Scan identifiers in the moved tree (same `tokenize` scan as WP21 T098 step 0, root `tests/charter_offering`). At base 193 files had a hit; most are the `pytest.mark.doctrine` marker and names already renamed by WP19/WP20.
  2. File names: `test_doctrine_validate_lang_guard.py` (it tests `charter validate`) → `test_charter_validate_lang_guard.py`; `test_doctrine_health_glossary_pack.py` (the pack health report) → `test_charter_pack_health_glossary_pack.py`. Keep `agent_profiles/test_doctrine_daphne_canonical_structure.py` (C-004), `test_testing_doctrine_single_owner.py` and `test_mattpocock_skill_doctrine.py` (content sense). Update every reference to a renamed file (`pyproject.toml`, `test_timing_coverage_invariant.py`, `.github/ci-shard-timings.json`).
  3. Function, class, fixture and helper names with the tier sense (for example a `doctrine_root` fixture that means the built-in pack root) take WP19's noun; names that test a removed surface (`spec-kitty doctrine …` unknown-command assertions) keep "doctrine".
  4. **The `doctrine` pytest marker** (`pytest.ini:60`, "Doctrine package smoke and integration checks"; used in about 199 files): decide and record. Recommended: keep the marker name in this mission (no CI filter selects it at base: `git grep -n "\-m [\"']*doctrine" -- .github Makefile scripts` is empty; renaming touches about 200 files and the marker-registry gates for no consumer gain) and reword its `pytest.ini` description to "Charter offering (src/charter/offering) smoke and integration checks". If you rename it instead, rename it everywhere in one commit and run the marker gates (`tests/architectural/test_marker_job_completeness.py`, `test_fast_tier_marker_completeness.py`, and any other file `git grep -l "pytest.ini" tests/architectural` shows reading the marker registry). `pytest.ini` is a shared file: log the edit.
  5. Re-run the scan; classify every remaining hit in the Activity Log (kept: reason).
- **Files**: `tests/charter_offering/**`, logged follow-ups.
- **Parallel?**: After T105.
- **Notes**: never merge, split or drop a test while renaming.
- **Validation**:
  - [ ] Collected-test count still equals the T105 baseline.
  - [ ] Classification recorded.

## Test Strategy

```bash
make test-fast
uv run --frozen pytest <every acceptance test id you un-xfailed> -q
uv run --frozen pytest tests/charter_offering tests/charter -q -m "fast or unit"   # owning subsystem dirs for src/charter/offering/**
uv run --frozen pytest tests/charter_offering tests/charter -q                     # full, once, before review
uv run --frozen pytest tests/next/test_discovery_step_contract.py tests/ci/test_corpus_blocking_home.py \
  tests/kernel/test_env_expand.py tests/dossier/test_manifest.py tests/docs/test_module_readme_lint.py \
  tests/cli/test_mission_agnostic_flag.py tests/runtime/next/test_composed_guard_launder.py \
  tests/integration/test_org_pack_chain_delivery.py tests/integration/test_mission_type_resolution_integration.py -q
uv run --frozen pytest tests/architectural/test_ci_corpus_trigger_completeness.py \
  tests/architectural/test_timing_coverage_invariant.py tests/architectural/test_ruff_format_exclude_ratchet.py \
  tests/architectural/test_pyproject_shape.py tests/architectural/test_no_legacy_terminology.py -q
# Roster bijection and marker gates (run those that exist):
ls tests/architectural/test_module_shard_registry.py tests/architectural/test_gate_selection_authority.py \
   tests/architectural/test_ci_collection_completeness.py tests/architectural/test_marker_job_completeness.py tests/architectural/test_fast_tier_marker_completeness.py 2>/dev/null \
   | xargs -r uv run --frozen pytest -q
uv run --frozen mypy --strict <touched .py files>
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
make docs-lint
```

## Risks & Mitigations

- **Moved tests stop running in CI**: a roster or path filter still names the old directory. Mitigation: one commit for move plus rosters; bijection gates; check `packs.yml` path filter by hand.
- **Ratchet growth**: renaming exclude entries out of sorted order or adding entries. Mitigation: run the ratchet gate; prefer formatting and dropping entries.
- **Follow-up edit of AGENTS.md (WP22, upstream)**: test-policy lines only; log it.
- **Lost history**: use `git mv` so `git log --follow` works.

## Review Guidance

- Confirm the WP23 acceptance tests were red after the first commit and green at the end, assertions unchanged.
- Compare file count and collected-test count before/after (Activity Log).
- Run the Objectives grep; any hit outside historical roots is a defect.
- Check the packs workflow still routes `src/charter/offering/**` changes to the moved tests.
- Check the marker decision is recorded with its reason.
- Check every follow-up edit in a non-owned file is logged.

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

Test file names still carrying the retired service/bundle names: `test_doctrine_service_*.py`, `test_action_doctrine_bundle_*.py`, `test_doctrine_service_builder_unification.py`, `test_charter_sole_door_doctrine_service.py`, plus test function names containing `doctrine_service` / `doctrine_bundle` (rename only where in your owned scope; otherwise list for WP25).
- From WP20 review: `tests/charter/test_compact.py` local `offering_root = tmp_path/".kittify"/"doctrine"` holds a project pack root — use `project_pack_root` and the flat `.kittify/charter-packs`; test name still says `doctrine_directory`.
