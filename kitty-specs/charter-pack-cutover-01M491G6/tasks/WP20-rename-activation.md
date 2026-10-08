---
work_package_id: WP20
title: Identifier rename R2 — activation
dependencies:
- WP19
requirement_refs:
- FR-010
planning_base_branch: issue-3732-charter-pack-rename
merge_target_branch: issue-3732-charter-pack-rename
branch_strategy: Planning artifacts for this mission were generated on issue-3732-charter-pack-rename. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-3732-charter-pack-rename unless the human explicitly redirects the landing branch.
subtasks:
- T095
- T096
- T097
phase: Phase 5 - Names
history:
- at: '2026-10-06T19:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: lexical-larry
authoritative_surface: src/charter/activation/
create_intent:
- src/charter/activation/_project_root_candidates.py
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/active_charter_service_builder.py
execution_mode: code_change
owned_files:
- src/charter/activation/__init__.py
- src/charter/activation/_activation_render.py
- src/charter/activation/_catalog_miss.py
- src/charter/activation/action_doctrine_bundle.py
- src/charter/activation/cascade.py
- src/charter/activation/catalog.py
- src/charter/activation/charter_md_parsing.py
- src/charter/activation/compact.py
- src/charter/activation/context.py
- src/charter/activation/context_contract.py
- src/charter/activation/context_json.py
- src/charter/activation/context_renderers/activation_block.py
- src/charter/activation/context_renderers/artifact_bodies.py
- src/charter/activation/context_renderers/authority_paths.py
- src/charter/activation/context_renderers/bootstrap_text.py
- src/charter/activation/context_renderers/catalog_diagnosis.py
- src/charter/activation/context_renderers/compact_governance.py
- src/charter/activation/context_renderers/delivery_table.py
- src/charter/activation/context_renderers/profile_sections.py
- src/charter/activation/context_renderers/reference_pointers.py
- src/charter/activation/context_renderers/selection_block.py
- src/charter/activation/context_renderers/token_budget.py
- src/charter/activation/context_result_builders.py
- src/charter/activation/context_state.py
- src/charter/activation/doctrine_service_builder.py
- src/charter/activation/invocation_context.py
- src/charter/activation/language_advisory.py
- src/charter/activation/language_scope.py
- src/charter/activation/language_vocabulary.py
- src/charter/activation/manifest_loader.py
- src/charter/activation/neutrality/__init__.py
- src/charter/activation/neutrality/language_scoped_allowlist.yaml
- src/charter/activation/neutrality/lint.py
- src/charter/activation/org_expected_artifacts.py
- src/charter/activation/org_pack_discovery.py
- src/charter/activation/profile_resolution.py
- src/charter/activation/progressive_disclosure.py
- src/charter/activation/reference_resolver.py
- src/charter/activation/resolver.py
- src/charter/activation/schemas.py
- src/charter/activation/scope_router.py
- src/charter/activation/skill_preparation.py
- src/charter/activation/synthesizer/_constants.py
- src/charter/activation/synthesizer/artifact_naming.py
- src/charter/activation/synthesizer/generated_artifact_adapter.py
- src/charter/activation/synthesizer/interview_mapping.py
- src/charter/activation/synthesizer/request.py
- src/charter/activation/template_resolver.py
- src/charter/activation/_project_root_candidates.py
- src/charter/activation/action_governance_bundle.py
- src/charter/activation/active_charter_service_builder.py
- tests/architectural/test_charter_sole_door_inner_reacharound.py
- tests/architectural/test_charter_sole_door_resolver_imports.py
- tests/architectural/test_dead_builtin_doc_paths.py
- tests/architectural/test_no_config_key_spelled_as_module_path.py
- tests/architectural/test_no_op_stable_writes.py
- tests/architectural/test_org_activation_seam.py
- tests/charter/context_renderers/test_include_selector_widening.py
- tests/charter/test_action_bundle_delivery.py
- tests/charter/test_action_bundle_tension_arbiters.py
- tests/charter/test_action_doctrine_bundle_activation.py
- tests/charter/test_action_doctrine_bundle_org_fragment.py
- tests/charter/test_action_gate_single_load.py
- tests/charter/test_activation_consumers.py
- tests/charter/test_active_languages_idempotency.py
- tests/charter/test_call_site_propagation.py
- tests/charter/test_catalog.py
- tests/charter/test_charter_context_directives_source.py
- tests/charter/test_charter_context_spdd_reasons.py
- tests/charter/test_compiler.py
- tests/charter/test_config_sourced_derivation.py
- tests/charter/test_config_stem_parity.py
- tests/charter/test_consistency_check.py
- tests/charter/test_context_authority_paths.py
- tests/charter/test_context_display_charter_md.py
- tests/charter/test_context_include_activation.py
- tests/charter/test_context_org_chain.py
- tests/charter/test_context_profile.py
- tests/charter/test_context_profile_lineage_parity.py
- tests/charter/test_context_prose_presence_pin.py
- tests/charter/test_context_unknown_language.py
- tests/charter/test_directive_unresolved_token_warning.py
- tests/charter/test_directives_additive_regression.py
- tests/charter/test_doctrine_governance_coverage.py
- tests/charter/test_doctrine_service_builder_unification.py
- tests/charter/test_drg_activation_gate.py
- tests/charter/test_emit_delivery_bind.py
- tests/charter/test_glossary_delivery_render.py
- tests/charter/test_glossary_include_activation.py
- tests/charter/test_kind_cascade_exhaustive.py
- tests/charter/test_kind_vocabulary.py
- tests/charter/test_merged_graph_on_live_path.py
- tests/charter/test_phase3_integration.py
- tests/charter/test_presence_gate_bundle_authority.py
- tests/charter/test_reference_block.py
- tests/charter/test_resolve_project_governance_single_authority.py
- tests/charter/test_resolved_mission_type_context.py
- tests/charter/test_resolver.py
- tests/charter/test_resolver_activation_gating.py
- tests/charter/test_resolver_activation_parity.py
- tests/charter/test_resolver_directive_activation_keying.py
- tests/charter/test_resolver_tier_axis_via_factory.py
- tests/charter/test_schemas.py
- tests/charter/test_schemas_additive_fields.py
- tests/charter/test_template_resolver.py
- tests/cli/commands/test_reconcile.py
- tests/docs/test_asset_resolution_wheel.py
- tests/docs/test_runtime_read_resolution.py
- tests/dossier/test_manifest.py
- tests/dossier/test_rebaseline.py
- tests/glossary/test_canonical_promotion.py
- tests/runtime/next/test_presence_filenames.py
- tests/runtime/test_resolver_unit.py
- tests/specify_cli/charter_runtime/test_boundary_heal.py
- tests/specify_cli/cli/commands/test_charter_ambiguous_directives.py
- tests/specify_cli/cli/commands/test_charter_org_directive_identity.py
- tests/specify_cli/invocation/test_org_profiles.py
- tests/specify_cli/mission_step_contracts/test_executor.py
- tests/specify_cli/skills/test_pack_skill_activation_coherence.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP20 – Identifier rename R2 — activation

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `lexical-larry`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

(After WP18 the skill is `spk-charter-profile-load`; also load the bulk-edit skill, `spk-practice-bulk-edit`.)

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

FR-010, slice R2 of `research/package-split-and-paths.md` §C: `src/charter/activation/**` holds the largest share of retired-tier identifiers (42 files / 550 tokens at plan time). Rename the retired-tier sense, resolve the activation-side `DoctrineService` homonym, and rename the three `*doctrine*` modules (T096; occurrence map C19), with no aliases or shim modules (C-001).

Done means:

- The R2 table below is applied at definitions and at every call site in the repository (activation, `charter/__init__.py` facade, `specify_cli`, `runtime`, tests, patch strings), one symbol family per commit, tree importable at each commit.
- `charter.activation.resolver.DoctrineService` is `ActiveCharterService` (or the name WP19 recorded for the wrapper; read WP19's Activity Log first) and nothing named `DoctrineService` remains anywhere.
- The modules `_doctrine_paths.py`, `doctrine_service_builder.py`, `action_doctrine_bundle.py` are moved (`git mv`) to their new names; no stub module stays at the old path.
- Content-sense "doctrine" is kept; tier-sense prose renamed (T097).
- WP01 acceptance test `test_fr010_retired_identifiers_absent[r2]` (marked `pending_until("WP20")`: the closed R2 identifier list, scanned over `src/charter/activation/**`) goes red → green.

### R2 rename table (proposed; record the final choice)

| Before | After | Notes |
|---|---|---|
| `charter.activation.resolver.DoctrineService` (activation-aware wrapper) | `ActiveCharterService` | Homonym of the offering class WP19 renamed to `CharterOfferingService`. Filters the offering by the project's **active charter**; pairs with WP17's `ActiveCharterManager`. Remove the local aliases `ActivationAwareDoctrineService` / `_ActivationAwareDoctrineService` / `RawDoctrineService` at call sites (`doctrine_service_builder.py:80,236`, `compiler.py:1091-1092`, `charter_runtime/lint/checks/org_layer.py:307`, `cli/commands/_doctrine_{asset,collect}.py` or their successors) and import the distinct names directly. |
| module `charter.activation.doctrine_service_builder` | `charter.activation.active_charter_service_builder` | T096 |
| `build_activation_aware_doctrine_service` | `build_active_charter_service` | public builder; 12 files use it |
| `_build_activation_aware_doctrine_service` | `_build_active_charter_service` | patch seam via `charter.activation.context` (module docstring of the builder explains the single-patch-point contract — keep the seam, rename it) |
| `_build_doctrine_service` | `_build_offering_service` | builds the raw `CharterOfferingService`; patched by tests as `charter.activation.context._build_doctrine_service` |
| `_maybe_build_doctrine_service` (`context_json.py:186`) | `_maybe_build_offering_service` | |
| module `charter.activation.action_doctrine_bundle`, `_ActionDoctrineBundle`, `_load_action_doctrine_bundle`, locals `doctrine_bundle` | `charter.activation.action_governance_bundle`, `_ActionGovernanceBundle`, `_load_action_governance_bundle`, `governance_bundle` | Not "charter bundle": **Charter Bundle** is the canonical name of the `.kittify/charter/` tree (spec Domain Language). |
| module `charter.activation._doctrine_paths` | `charter.activation._project_root_candidates` | holds `_PROJECT_ROOT_CANDIDATES` / `resolve_project_root` (WP02 already points its first candidate at the kernel pack root) |
| `DoctrineCatalog`, `load_doctrine_catalog`, `resolve_doctrine_root` (`catalog.py:30,51,163`) | `OfferingCatalog`, `load_offering_catalog`, `resolve_offering_root` | re-exported lazily by `src/charter/__init__.py:57-58,159-160`; `resolve_offering_root` returns the `charter.offering` package dir |
| `doctrine_root` params/locals meaning the offering package root (`compiler.py` 32, `consistency_check.py` 12, `kind_vocabulary.py` 27, `drg_activation.py` 6, `reference_pointers.py` 6, `reference_resolver.py`, `resolver.py`, `catalog.py`) | `offering_root` | same meaning as WP19's rename; verify per site (a `doctrine_root` that is the *project* layer is `project_pack_root`) |
| `DoctrineSelectionConfig` (`schemas.py:92`), locals `doctrine_selection`, `_load_doctrine_selection` | `GovernanceCharterConfig`, `charter_config`, `_load_governance_charter_config` | The class models the `governance.charter` block (field `charter:` on `GovernanceConfig`). Do **not** use "Charter Selection": FR-013 retires that term. Re-exported by `src/charter/__init__.py:83,180`. |
| `doctrine_kind_subdir` (`synthesizer/artifact_naming.py:59`) | `pack_kind_subdir` | kind subdirectory under the project pack root |
| `_project_has_doctrine_overrides` (`mission_type_profiles.py:1353`) | `_project_has_pack_overrides` | follow-up (WP14 owns the file) |
| `_collect_all_doctrine_ids`, `all_doctrine_ids`, `missing_from_doctrine` (`consistency_check.py`) | `_collect_all_offering_ids`, `all_offering_ids`, `missing_from_offering` | follow-up (WP17 owns the file) |
| `_render_doctrine_artifact_include` (`context_renderers/template_include.py:229`) | `_render_offering_artifact_include` | follow-up (WP17) |
| `_doctrine_repository` (`manifest_loader.py:157`) | `_offering_template_repository` | |
| `overlay_doctrine_dir`, `doctrine_dir` (synthesizer, when it is the project pack root) | `overlay_pack_dir`, `pack_dir` | |
| `_default_doctrine_service` (`compiler.py:1036`) | `_default_active_charter_service` | follow-up (WP09 owns `compiler.py`) |
| `MissingDoctrinePackError` | — | **deleted by WP05** (dead code, approved); nothing to rename; the r2 scan already finds it absent |

**Keep (content sense or persisted)** — record each in the Activity Log:

- `apply_doctrine_intent_aliases` (`interview.py:692`, "Select doctrine implied by well-known user shorthand") — selects governance content: content sense, keep.
- `render_profile_suggested_doctrine` (`profile_sections.py:454`) and `_ACTION_DOCTRINE_LINK_WHEN` / `_render_action_doctrine_lines` (`selection_block.py:94`, `bootstrap_text.py:115`): judge by what they render. If they label governance content for an action ("action doctrine"), keep; if they name the tier, rename. Record.
- `propose_doctrine_changes` (`schemas.py:167`, `RetrospectiveGovernancePermissions`) — a persisted `charter.yaml` key meaning "propose changes to governance content": keep (not in the FR-012 inventory; renaming would need a migration).
- `doctrine_snapshot` (`synthesizer/request.py:143,261`, also `synthesize_pipeline.py`, `resynthesize_pipeline.py`): it is serialized into the synthesis request. Before renaming, check whether that serialization reaches persisted state or a content hash (`rg -n doctrine_snapshot src tests`, synthesis manifest/provenance writers). If it does, keep it and record; if it is in-memory only, rename to `offering_snapshot`.
- Mission-slug citations, ADR names, `doctrine-daphne`, `DIRECTIVE_039`.

## Context & Constraints

- Read: `.kittify/charter/charter.md`; `spec.md` FR-010, FR-013 (retired glossary terms incl. "Charter Selection"), C-001, C-004; `occurrence_map.yaml` (`code_symbols`, `import_paths` rename incl. C16 both homonyms and C19 `*_doctrine_*` modules; `user_facing_strings` manual_review); `research/package-split-and-paths.md` §C (R2 row; split R2a/R2b if > ~30 files of *identifier* change: if you need to, do catalog/service-builder first, synthesizer/context second, as separate commit series).
- WP19 is done: read its Activity Log for the recorded homonym names and any deviations from its proposed table. Use exactly the recorded wrapper name.
- **Not owned, edit as logged follow-ups** (owners are upstream of this WP via WP19 → WP14/WP17 → …, except where noted): `src/charter/__init__.py` (WP04; lazy facade map and `__all__`), `src/charter/activation/_doctrine_paths.py` (WP02; you `git mv` it — the destination is yours), `src/charter/activation/synthesizer/{__init__,graph_residue}.py` (WP03), tests `tests/charter/{test_directive_identity_mapping,test_iter_org_charter_docs}.py` (WP05), `tests/specify_cli/charter_freshness/test_computer.py`, `tests/specify_cli/cli/commands/charter/test_synthesize_cli_reconcile.py` and all of `tests/charter/synthesizer/**` (WP03; patch strings for the builders live there), `src/charter/activation/{_drg_helpers,kind_vocabulary,pack_manager,mission_type_profile_repository}.py` and `synthesizer/{project_drg,resynthesize_pipeline}.py` (WP02), `synthesizer/{write_pipeline,path_guard,manifest,reconcile,staging,validation_gate}.py` and `project_registration.py` (WP03/WP04), `synthesizer/{provenance,synthesize_pipeline}.py` (WP04), `activation_engine.py`, `interview.py` (WP06), `compiler.py` (WP09), `sync.py`, `mission_type_profiles.py` (WP14), `action_grain.py`, `drg_activation.py` (WP15), `pack_context.py`, `activations.py`, `consistency_check.py`, `scope.py`, `context_renderers/template_include.py` (WP17), `synthesizer/errors.py` (WP03), `org_charter.py`, `layer_roots.py`, `effective_set.py` (WP02/WP05/WP06), and every `specify_cli` / `runtime` importer (WP21 owns the `specify_cli` command modules later and runs strictly after this WP): `runtime/next/runtime_bridge_io.py`, `specify_cli/doctrine_service_factory.py` (WP21 renames/deletes this module: you only fix the import it re-exports), `charter_runtime/lint/checks/org_layer.py`, `cli/commands/charter/{__init__,_fresh_doctrine,_resynthesis_preflight,_synthesis,activate,context,deactivate,generate,interview,pack,synthesize}.py`, `cli/commands/init.py`, `cli/commands/profiles_cmd.py`, `invocation/{org_profiles,registry}.py`, `mission_step_contracts/executor.py`, `runtime/resolver.py`, `tool_surface/bundles/claude.py`, `tool_surface/profiles/projection.py`, `upgrade/migrations/m_unify_charter_activation.py` (body only; ids/classes kept), `src/specify_cli/.contextive/governance.yml`, skill prose in `src/charter/offering/skills/**` (WP18), `src/charter/offering/{artifact_kinds,drg/migration/id_normalizer,drg/org_pack_config}.py` docstrings, and tests under `tests/doctrine/**` (WP23 later).
- **No parallel lane**: every owner named above is upstream of this WP (WP09, WP15, WP16 and WP18 through WP19), so these are logged follow-ups.
- **Do not edit WP01's `tests/acceptance/charter_pack_cutover/_effective_set.py`** (its digest is pinned in the golden header). It imports `build_activation_aware_doctrine_service` from `charter.activation.doctrine_service_builder`, which you rename: before your rename commit, ask the orchestrator for the WP01 follow-up (fixed helper, regenerated golden, logged); do not patch the helper yourself.
- Code style: ruff + mypy clean; `ruff format --check --force-exclude`; complexity ≤ 15; no new suppressions. `pyproject.toml` `[tool.ruff.format].exclude` lists `src/charter/activation/_doctrine_paths.py` (l.315), `action_doctrine_bundle.py` (l.317), `doctrine_service_builder.py` (l.332): when you move a module, either rename its entry at the sorted position or format the moved file and drop the entry (preferred: a shrink). `test_every_exclude_entry_exists_on_disk` and `tests/architectural/test_ruff_format_exclude_ratchet.py` enforce this. `pyproject.toml` is a shared file: one-line edits, logged.

## Branch Strategy

- **Strategy**: lane per `lanes.json` (filled by finalize)
- **Planning base branch**: `issue-3732-charter-pack-rename`
- **Merge target branch**: `issue-3732-charter-pack-rename`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Red-first commit (C-006 / C-011)

```bash
rg -n 'pending_until\("WP20"\)' tests/acceptance/charter_pack_cutover/
```

WP01 T008's `test_fr010_retired_identifiers_absent[r2]`: an AST/token scan of `src/charter/activation/**` for the closed R2 list in `tests/fixtures/charter_pack_cutover/retired_identifiers.yaml` (for example `DoctrineCatalog`, `DoctrineSelectionConfig`, `_doctrine_paths`, `doctrine_service_builder`, `action_doctrine_bundle`, `MissingDoctrinePackError`), with a planted-identifier self-test and a scanned-file floor. Remove the markers only; run; confirm red; commit `test(acceptance): unmark WP20 FR-010 R2 tests (red) (#3732)`.

## Subtasks & Detailed Guidance

### Subtask T095 – R2 rename: activation identifiers (`DoctrineService` homonym resolved)

- **Purpose**: activation-side identifiers carry the charter vocabulary; the wrapper gets a distinct name.
- **Steps**:
  1. Re-measure (same tokenizer script as WP19, root `src/charter/activation`); record before-counts in the Activity Log.
  2. Wrapper first: `resolver.py:170` `class DoctrineService` → `ActiveCharterService`; `__all__` (l.68); docstrings (l.6-30, 99, 171, 182, 407); `resolve_governance_for_profile(doctrine_service: DoctrineService, …)` (l.992-1007) → parameter `charter_service`. Then every importer: `rg -n "activation\.resolver import|resolver\.DoctrineService" src tests`. Run `uv run mypy src/charter src/specify_cli src/runtime` after this family.
  3. Builders (T096 moves the module; rename the functions in the same series): `build_activation_aware_doctrine_service`, `_build_activation_aware_doctrine_service`, `_build_doctrine_service`, `_maybe_build_doctrine_service`. Patch strings in tests are the main breakage risk: `rg -n "_build_doctrine_service|build_activation_aware_doctrine_service" tests` and update every `monkeypatch.setattr("…")` / `mock.patch("…")` target, including the `charter.activation.context._build_doctrine_service` seam that `doctrine_service_builder`'s docstring documents.
  4. Catalog family (`catalog.py`) and its facade entries in `src/charter/__init__.py` (lazy map l.57-58 and `__all__` l.159-160). The lazy map must not keep an old key.
  5. `DoctrineSelectionConfig` family (`schemas.py:92`, `org_pack_discovery.py:290`, renderers `activation_block.py`, `authority_paths.py`, `bootstrap_text.py`, `compact_governance.py`, `selection_block.py`, `context_result_builders.py`; facade `charter/__init__.py:83,180`). Its docstring's parity rule ("field naming MUST mirror the `DoctrineService` property name", pinned by `test_artifact_selection_completeness.py`) now refers to `CharterOfferingService`; that test file no longer exists (only `tests/architectural/README.md` still names it); find the live parity guard, if any, with `rg -ln "selected_styleguides|DoctrineSelectionConfig" tests`, update the class name it introspects, and correct the stale citation in the docstring (record what you found).
  6. `doctrine_root` → `offering_root` where it means the offering package root; `doctrine_dir` / `overlay_doctrine_dir` → `pack_dir` / `overlay_pack_dir` where it means the project pack root. Check each site's meaning (read the function, do not sed blindly).
  7. Keep-list items: leave and record (see Objectives).
- **Files**: owned activation files; follow-ups listed in Context.
- **Parallel?**: Families are sequential commits (the wrapper first).
- **Validation**: [ ] `rg -nw "DoctrineService|ActivationAwareDoctrineService|RawDoctrineService" src tests` empty; [ ] `uv run mypy src/charter src/specify_cli src/runtime` clean.

### Subtask T096 – R2 module renames (`_doctrine_paths`, `doctrine_service_builder`, `action_doctrine_bundle`)

- **Purpose**: module paths stop naming the retired tier (occurrence map `import_paths: rename`, C19).
- **Steps**:
  1. `git mv src/charter/activation/doctrine_service_builder.py src/charter/activation/active_charter_service_builder.py`; `git mv src/charter/activation/action_doctrine_bundle.py src/charter/activation/action_governance_bundle.py`; `git mv src/charter/activation/_doctrine_paths.py src/charter/activation/_project_root_candidates.py`. (`_doctrine_paths.py` may also be listed by WP02 as a READ site it repointed; WP02 is upstream and done, so the move is safe.)
  2. Repoint every import: `rg -n "doctrine_service_builder|action_doctrine_bundle|_doctrine_paths" src tests scripts .github pyproject.toml`. Known: `charter/activation/{compact,language_vocabulary,context,context_json,skill_preparation,pack_manager,profile_resolution,context_renderers/template_include}.py`, `cli/commands/_doctrine_asset.py` (or its WP15/WP16 successor), `specify_cli/doctrine_service_factory.py`, architectural gates (`tests/architectural/_sole_door_scan.py:69` `UNIFIED_BUILDER_REL_PATH`, `test_charter_sole_door_doctrine_service.py:157` `RAW_BUILDER_QUALNAME` and messages l.47-513, `test_charter_sole_door_agent_profile_repository.py:15,58,104`).
  3. Gates that key modules by path or qualname: `tests/architectural/dead_symbol_allowlist.yaml`, `test_no_dead_modules.py`, the runtime/charter boundary lazy baseline (`test_runtime_charter_doctrine_boundary.py`), `test_charter_sole_door_*`: re-key to the new module paths (counts unchanged, never grow). These gate files are owned by other WPs (WP05/WP19/WP21): logged follow-ups.
  4. `pyproject.toml` format-exclude entries (Context).
  5. No stub module at the old path; `uv run python -c "import charter.activation.doctrine_service_builder"` must fail with `ModuleNotFoundError`.
- **Files**: the three moves (`owned_files` holds both old and new paths).
- **Parallel?**: After T095's builder family (so the moved file already carries the new function names), or in the same commit.
- **Validation**: [ ] `uv run pytest tests/architectural/test_charter_sole_door_doctrine_service.py tests/architectural/test_charter_sole_door_agent_profile_repository.py tests/architectural/test_ruff_format_exclude_ratchet.py -q` green.

### Subtask T097 – R2 tests and docstrings

- **Purpose**: tests follow; tier-sense prose in activation renamed.
- **Steps**:
  1. Owned tests (frontmatter; 86 files at plan time) import, patch or assert R2 names: update. Keep test **file** names (WP23 T106 renames residual test identifiers and files), but rename test functions/fixtures/locals that describe the retired tier where you touch them.
  2. Not-owned tests that also need the rename (logged): `tests/doctrine/**`, WP17-owned charter tests, `tests/specify_cli/test_doctrine_service_factory.py` (WP21), `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` and `tests/specify_cli/upgrade/test_unify_charter_activation_migration.py` (WP06/WP10), `tests/specify_cli/cli/commands/charter/test_charter_pack_builtin.py` (WP08), `tests/charter/synthesizer/test_write_pipeline.py`, `test_synthesize_path_parity.py`, `tests/charter/test_synthesis_provenance_paths.py` (WP03), `tests/architectural/{test_kind_table_derivation,test_no_dead_cli_paths,_dead_path_scan,test_no_dead_src_path_literals,test_built_in_location_authority}.py`, `tests/release/coverage_breadth_baseline.json` (module keys).
  3. Prose: apply the WP19 classification rule (tier sense → rename; content sense, mission slugs, ADR names → keep) to docstrings, comments and the YAML in owned activation files (`neutrality/language_scoped_allowlist.yaml`: check entries are not identifiers of the scan itself). Examples of tier sense here: `_doctrine_paths.py` docstring "Shared DoctrineService project-root candidate resolution", "project-doctrine directory", "Phase 3 synthesis target `.kittify/doctrine/`" (already pointed at the kernel root by WP02), `catalog.py` "Deterministic doctrine catalog derived from on-disk doctrine assets" → "offering catalog … built-in artifacts", `resolve_offering_root` docstring "Resolve the doctrine package root…" → "charter.offering package root". Content sense: "doctrine selected by the interview", "governing doctrine for an action".
  4. Record a classification summary (counts per class, plus each non-obvious judgment) in the Activity Log.
  5. Run the WP20 acceptance tests: green. Commit series ends with `refactor(charter)!: activation identifiers use the charter vocabulary (#3732)`.
- **Validation**: [ ] `rg -n 'pending_until\("WP20"\)' tests` empty; [ ] tokenizer re-measure shows only keep-list identifiers left in `src/charter/activation/**`.

## Test Strategy

```bash
make test-fast
uv run pytest tests/acceptance/charter_pack_cutover/ -q                  # WP20-marked tests at least
uv run pytest tests/charter/ tests/doctrine/ -q                          # owning subsystems (activation + offering imports)
uv run pytest tests/runtime/ tests/specify_cli/charter_runtime/ tests/specify_cli/cli/commands/charter/ \
              tests/specify_cli/invocation/ tests/specify_cli/mission_step_contracts/ tests/dossier/ \
              tests/docs/test_asset_resolution_wheel.py tests/docs/test_runtime_read_resolution.py \
              tests/glossary/test_canonical_promotion.py tests/cli/commands/test_reconcile.py -q
uv run pytest tests/architectural/test_charter_sole_door_doctrine_service.py \
              tests/architectural/test_charter_sole_door_agent_profile_repository.py \
              tests/architectural/test_charter_sole_door_inner_reacharound.py \
              tests/architectural/test_charter_sole_door_resolver_imports.py \
              tests/architectural/test_charter_facades_reexport_doctrine.py \
              tests/architectural/test_doctrine_public_surface.py \
              tests/architectural/test_org_activation_seam.py \
              tests/architectural/test_charter_offering_does_not_import_activation.py \
              tests/architectural/test_charter_no_specify_cli_import.py \
              tests/architectural/test_layer_rules.py \
              tests/architectural/test_no_dead_modules.py \
              tests/architectural/test_no_dead_symbols.py \
              tests/architectural/test_runtime_charter_doctrine_boundary.py \
              tests/architectural/test_ruff_format_exclude_ratchet.py \
              tests/architectural/test_no_legacy_terminology.py -q
uv run ruff check src tests
uv run ruff format --check --force-exclude <touched .py files>
uv run mypy src/charter src/specify_cli src/runtime
```

Never bare `tests/architectural/` or `make test-full`.

## Risks & Mitigations

- **Patch-string breakage** (tests patch `charter.activation.context._build_doctrine_service`): a missed string makes a test patch nothing and pass vacuously or fail obscurely. Mitigation: grep bare strings; run the owning test directories in full.
- **Homonym crossing**: rename by import origin; mypy after each family.
- **Persisted key renamed by accident** (`propose_doctrine_changes`, `doctrine_snapshot`): keep-list with explicit checks.
- **"Charter Bundle" / "Charter Selection" collisions**: the table avoids both; reviewer checks.

## Commit checkpoints

This WP stays one WP (mechanical; orchestrator ruling AR-S8), but a session may stop after any checkpoint and resume at the next. Commit at each, with the tree importable and the touched tests green, and append one Activity Log line naming the checkpoint:

1. red-first commit;
2. T095, one commit per symbol family of the R2 table (the wrapper `ActiveCharterService` first, then the builders, the catalog, `DoctrineSelectionConfig`, the remaining rows; `MissingDoctrinePackError` was deleted by WP05);
3. T096, one commit per module move (`_doctrine_paths`, `doctrine_service_builder`, `action_doctrine_bundle`);
4. T097, tests and docstrings, then the green acceptance run.

A resuming session reads the Activity Log, checks `git log --oneline` against this list and continues with the next unchecked item.

## Review Guidance

- Red-on-base → green-on-final for the WP20 acceptance tests.
- No `DoctrineService` (either homonym) anywhere; distinct names match WP19's record.
- The three modules moved with no stub left; imports and gates re-keyed; format-exclude entries renamed or dropped (never grown).
- Keep-list decisions recorded with reasons; content-sense prose intact.
- Follow-up edits logged with the owner's status at edit time.
- mypy over `src/charter src/specify_cli src/runtime` clean; format check with `--force-exclude`.

## Definition of Done

- [ ] Red-first commit, then green.
- [ ] R2 table applied with all call sites; homonym resolved; no aliases.
- [ ] Three module moves done; no shim modules.
- [ ] Tests and gates follow; classification summary recorded.
- [ ] Commands above run and recorded; terminology gate green.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END**
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (`date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-10-06T19:30:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.

## Carry-over from WP19

- Rename the activation wrapper `charter.activation.resolver.DoctrineService` → **`ActiveCharterService`** (WP19 renamed the raw offering class to `CharterOfferingService`), including bare `DoctrineService` mentions in activation code and tests; `id_normalizer.py:~7`, `org_pack_config.py:~486`.
- Sole-door gate: drop `"DoctrineService"` from `DOCTRINE_SERVICE_CANDIDATE_NAMES` and rename `WRAPPER_DOCTRINE_SERVICE_QUALNAME`.
- Rename the `doctrine_root` keyword on `resolve_config_id` and related functions (WP19 used `pack_root` for the extractor/overlay/bundle sites; keep naming consistent).
