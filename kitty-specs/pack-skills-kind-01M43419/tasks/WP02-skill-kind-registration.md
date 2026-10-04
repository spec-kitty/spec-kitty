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

