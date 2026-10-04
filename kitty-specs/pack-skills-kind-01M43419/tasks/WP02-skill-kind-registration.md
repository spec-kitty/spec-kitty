---
work_package_id: WP02
title: "Register the `skill` kind \u2014 enum, NodeKind, schema, model, repository,\
  \ doctor health"
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-015
- SC-008
- SC-009
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/pack_skills/
create_intent:
- src/charter/offering/pack_skills/__init__.py
- src/charter/offering/pack_skills/models.py
- src/charter/offering/pack_skills/repository.py
- src/charter/offering/schemas/skill.schema.yaml
- tests/doctrine/pack_skills/test_pack_skill_kind.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/offering/drg/models.py
- src/charter/offering/pack_skills/**
- src/charter/offering/schemas/skill.schema.yaml
- src/charter/offering/drg/migration/extractor.py
- src/charter/activation/context_renderers/delivery_table.py
- src/specify_cli/cli/commands/_doctrine_health.py
- src/specify_cli/cli/commands/_doctrine_collect.py
- tests/doctrine/pack_skills/**
- src/specify_cli/doctrine/org_charter.py
- src/charter/activation/pack_context.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Register the `skill` kind — enum, NodeKind, schema, model, repository, doctor health

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-003, FR-004, FR-005, FR-015, SC-008, SC-009 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP02 --agent claude`.

## Subtasks

### T006

Add `ArtifactKind.SKILL` (plural `skills`, pattern `*.skill.yaml`, has_built_in_content_dir True → `packs/built-in/skills/` may be absent/empty, PROJECT_KIND_DIRS `skills`, activatable, org_requirable True, selection_overlayable False). Cross-edit of artifact_kinds.py (WP01-owned) is expected. Add `NodeKind.SKILL`. Update every exact-set/totality test the brownfield map lists (tests/doctrine/test_artifact_kinds.py, drg/test_kind_mapping_totality.py, drg/test_nodekind_artifactkind.py, tests/charter/test_kind_vocabulary*.py, test_direct_write_kinds_parity.py, test_kind_cascade_exhaustive.py, test_charter_whole_kind_invariants.py, tests/architectural/test_charter_kind_vocabulary_single_authority.py …) — run them to find all.

### T007

Pydantic model `PackSkill` (pack_skills/models.py): schema_version, id, title, description, triggers, form (`prompt`|`wrapper`, discriminated: prompt needs body_path; wrapper needs expands_to{target, args}), parameters[{name, required, description}], invocation{user_invocable, model_invocable (forced False when side_effects non-empty), side_effects}, tools, version, maintainers, overrides/enhances. skill.schema.yaml mirroring it (kernel/schema_utils resolution).

### T008

Validator: for org/project tiers refuse a `scripts/` dir next to the skill and any permission-widening frontmatter key (`allowed-tools`) in the body; refuse ids/rendered names starting with `spk-`, `spec-kitty-`, `spec-kitty.` for non-built-in tiers; `cli:` targets limited to `spec-kitty` argv.

### T009

`PackSkillRepository` (BaseDoctrineRepository subclass) loading built-in/org/project tiers; same id in two sibling org packs → hard conflict error; overrides/enhances per ADR (enhances may change defaults/triggers/tools/narrow invocation, never body or expansion). Wire service property `skills` (service.py) and resolver activation filter. Extractor `_emit_skill_nodes` (precedent `_emit_glossary_pack_nodes` extractor.py:896) — built-in shard stays empty. Delivery table entry `slot=None` with reason. Org DRG fragments may declare skill nodes + `requires`/`suggests` edges.

### T010

Doctor health dimension `PackSkillHealth` (loaded/skipped) in _doctrine_health.py/_doctrine_collect.py mirroring GlossaryPackHealth; unhealthy when any skipped. Tests in tests/doctrine/pack_skills/ for every branch (forms, reserved prefixes, scripts/, allowed-tools, sibling conflict, enhances limits, health).

## Amendments (post-tasks anti-laziness squad — binding)

- Kind registration is gate-complete in this WP: together with `ArtifactKind.SKILL` (activatable, org_requirable, NOT selection_overlayable — assert that) add `OrgCharterPolicy.required_skills` + `skill_namespace` (org_charter.py) and `PackContext.activated_skills` field + reader (pack_context.py) so WP01's derivation gates stay green at this commit. WP03 owns the semantics.
- Create `packs/built-in/skills/` empty with `.gitkeep` so built-in-dir totality tests hold.
- T008: test that a built-in-tier skill is exempt from reserved-prefix refusal.
- T010: `doctor doctrine --json` test asserting the skill health key exists, and unhealthy when a malformed skill is skipped.
- DoD: run tests/architectural/test_layer_rules.py.

## Definition of Done

- Every subtask done; new branches/helpers carry focused tests in the same commit (Sonar new-code gate).
- `ruff check`, `ruff format --check --force-exclude <changed files>`, `mypy` on changed modules: zero findings; complexity ≤15; no new suppressions.
- Targeted tests for touched modules plus owning subsystem dirs pass; record commands and counts in the activity log.
- Layer direction respected: `charter` never imports `specify_cli`.

## Risks

- Exact-set/totality tests across `tests/charter`, `tests/doctrine`, `tests/architectural` enumerate kinds — find them by running those directories' fast tier.
- Out-of-map edits are allowed only with a one-line rationale in the activity log.

## Reviewer Guidance

Verify each requirement in the objective has a non-vacuous test; reject no-op passes.

## Activity Log


- 2026-10-04 claude (python-pedro, WP02) -- implemented T006-T010. Commits: 068083b0 (kind registration), 377ba4d2 (model/schema/validator/repository/wiring), a17cc04d (doctor health).
  - Tests run (all in repo venv; counts are passed/failed):
    - `pytest tests/charter tests/doctrine tests/specify_cli/doctrine tests/architectural/{test_builtin_pack_provenance_ratchet,test_charter_facades_reexport_doctrine,test_charter_kind_vocabulary_single_authority,test_charter_no_specify_cli_import,test_charter_offering_does_not_import_activation,test_charter_sole_door_doctrine_service,test_charter_sole_door_inner_reacharound,test_dead_symbol_allowlist_contract,test_doctrine_census,test_doctrine_public_surface,test_doctrine_regenerate_graph_roundtrip,test_kind_table_derivation,test_layer_rules,test_no_dead_modules,test_no_dead_symbols,test_no_inert_schema_slots,test_no_legacy_terminology,test_pack_manifest_no_author_edit,test_runtime_charter_doctrine_boundary,test_glossary_pack_boundary,test_glossary_pack_parity,test_pack_lineage_no_parallel_resolver,test_completion_manifest_freshness}.py -m "fast or unit or architectural" -n auto --dist loadfile` -> 7947 passed, 33 skipped, 4 failed: 1 pre-existing (`test_pack_manager.py::test_preparation_refuses_broken_required_inputs[unreadable]`, root chmod) and 3 mine (dead-symbol x2, inert-slot) which were fixed afterwards.
    - Re-run of the three red gates + new tests: `pytest tests/doctrine/pack_skills tests/architectural/test_no_inert_schema_slots.py test_no_dead_symbols.py test_dead_symbol_allowlist_contract.py test_charter_no_specify_cli_import.py -n auto --dist loadfile` -> 143 passed, 1 skipped.
    - `pytest tests/doctrine/pack_skills tests/charter/test_pack_manager.py tests/doctrine/test_artifact_kinds.py tests/charter/test_pack_manager_catalog.py tests/architectural/test_kind_table_derivation.py tests/doctrine/test_charter_activatable_vocabulary.py tests/architectural/test_charter_sole_door_doctrine_service.py tests/architectural/test_layer_rules.py` -> 313 passed, 2 skipped (before the sole-door fix), then pack_skills + sole-door -> 98 passed, 1 skipped.
    - `spec-kitty doctrine regenerate-graph --check` -> fresh (built-in skill shard is empty, no file to commit).
    - `ruff check` + `ruff format --check --force-exclude` on all changed files: clean. `mypy` on the new package: only the 2 errors the glossary_packs precedent shows when mypy runs on a narrow path (`Class cannot subclass value of type "Any"`, `Returning Any` from `built_in_dir` Path) -- same class as on `glossary_packs/repository.py`; no other findings.
  - Out-of-map edits (rationale): `tests/architectural/test_kind_table_derivation.py`, `tests/charter/test_pack_manager.py`, `tests/charter/test_pack_manager_catalog.py`, `tests/doctrine/test_artifact_kinds.py`, `tests/doctrine/test_charter_activatable_vocabulary.py` -- exact-set/count expectations updated deliberately for the 11th activatable kind (YAML_KEY_MAP 10->11, merge_defaults 10->11 kinds, `skills` requirable but not overlayable / no `selected_skills`). `src/charter/activation/context_renderers/delivery_table.py`, `src/charter/activation/resolver.py`, `src/charter/offering/service.py`, `src/charter/offering/drg/migration/extractor.py`, `src/charter/activation/pack_context.py` -- the glossary_pack touchpoints the brief lists (delivery slot=None row + reason, gated `skills` property, service property, `_emit_skill_nodes`, `activated_skills` reader).
  - Deviations / notes:
    - Package is `src/charter/offering/pack_skills/` (WP brief), not `skills_kind/` as in plan.md.
    - Doctor collector reads through `build_activation_aware_doctrine_service(repo_root).raw_repository("skills")` instead of constructing the raw service (as `_collect_glossary_pack_health` does): the sole-door gate (`test_charter_sole_door_doctrine_service.py`) pins exactly six raw-construction sites, so a seventh was refused.
    - `apply_enhancement` rebuilds the merged `PackSkill` through its constructor (re-validated) rather than `model_copy`; besides correctness, it is the real producer the inert-slot gate needs for `form`, `expands_to`, `enhances`, `side_effects`, `user_invocable` (no baseline rows added).
    - `overrides`/`enhances` records fold into the catalog under the TARGET id; an `enhances` record keeps the base file as body source; overriding a built-in skill is refused (replaceable-builtins allowlist not wired for skills); `enhances` must restate form/body_path/expands_to unchanged.
    - Hand-off for WP03: `PackManager.merge_defaults` now writes `activated_skills: []` into an absent key (default pack has no skills) -- WP03's `effective_when_absent="required"` semantics must account for that. Helper names `_rendered_name`/`_RESERVED_PREFIXES` are private (dead-symbol gate) -- WP04's renderer may re-expose them.
    - Org DRG fragments declaring `skills` nodes + `requires`/`suggests` edges, and the `enhances` auto-emitted edge, are covered by `tests/doctrine/pack_skills/test_org_drg_skill_nodes.py` (2 passed); the kind needed no loader change (derived vocabulary).
    - Not done: no `skill.graph.yaml` shard (built-in tier is empty, so `regenerate-graph --check` is fresh and nothing to commit).
