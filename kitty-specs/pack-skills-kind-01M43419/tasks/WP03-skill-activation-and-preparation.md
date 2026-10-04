---
work_package_id: WP03
title: Skill activation, default-in-force, and prepare_skill_activations
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- FR-008
- SC-006
- SC-011
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/skill_preparation.py
create_intent:
- src/charter/activation/skill_preparation.py
- tests/charter/test_skill_activation.py
- tests/charter/test_skill_preparation.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/skill_preparation.py
- tests/charter/test_skill_activation.py
- tests/charter/test_skill_preparation.py
- src/specify_cli/charter_pack_registry.py
- src/charter/activation/schemas.py
- src/charter/activation/charter_yaml_io.py
- src/charter/activation/pack_manager.py
- src/charter/activation/resolver.py
- src/charter/activation/compiler.py
- src/specify_cli/cli/commands/charter/activate.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Skill activation, default-in-force, and prepare_skill_activations

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-006, FR-007, FR-008, SC-006, SC-011 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP03 --agent claude`.

## Subtasks

### T011

Config key `activated_skills` (derived via CHARTER_KIND_TOKENS / YAML_KEY_MAP; verify pack_manager, charter_yaml_io, `_NON_PACK_ACTIVATION_KEYS` in specify_cli/charter_pack_registry.py — add `activated_skills` there). PackContext field + reader.

### T012

Default in force (plan decision 5): add ArtifactKind fact `effective_when_absent` (`all` | `required`); SKILL = `required`. In pack_context three-state resolution, absent key for a `required` kind → effective = org `required_skills` ∪ built-in defaults (empty). `required_skills` + `skill_namespace` read charter-side via `_iter_org_charter_docs` (no specify_cli import); add `required_skills`/`skill_namespace` fields to OrgCharterPolicy (cross-edit). Test: absent key + activate X ⇒ required ∪ {X}.

### T013

Cascade: `charter activate skill X --cascade procedure,directive` follows DRG requires/suggests; deactivate keeps artifacts still referenced (C-005). Tests over a fixture org pack with a fragment.yaml declaring skill nodes and edges.

### T014

`prepare_skill_activations(pack_context/service, project_root-agnostic inputs) -> list[PreparedSkill]` pure: id, tier, rendered_name (`<namespace>-<id>`; project namespace from config key `charter_packs.project.skill_namespace`, refused with remedy if missing), form, body text or expansion (unresolved `builtin:` target), required URNs (from DRG requires edges), provenance (pack source path), `source_hash` = sha256 of JSON-canonical (sort_keys) record + body bytes. Duplicate rendered names → error before returning. Tests for each branch.

## Amendments (post-tasks anti-laziness squad — binding)

- WP03 also owns the `charter activate/deactivate skill` CLI token acceptance (activate.py); WP04 adds only the re-projection hook.
- T012 test fixture: ≥3 available skills, 1 required, activate X ⇒ effective == exactly {required, X}; plus regression: existing kinds still resolve `all` when absent.
- T013 SC-006 test: skill S1 and directive D both require procedure P; deactivate S1 with cascade ⇒ P stays active; control: P unshared ⇒ removed.
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

