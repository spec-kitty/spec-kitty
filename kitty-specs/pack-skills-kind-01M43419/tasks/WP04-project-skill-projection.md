---
work_package_id: WP04
title: Catalog seam and project-root projection through the managed installer
dependencies:
- WP03
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-013
- SC-001
- SC-003
- SC-007
- SC-010
- NFR-002
- NFR-004
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- src/specify_cli/skills/catalog.py
- src/specify_cli/skills/pack_skill_renderer.py
- tests/specify_cli/skills/test_pack_skill_projection.py
- tests/specify_cli/skills/test_pack_skill_renderer.py
- tests/architectural/test_skill_catalog_seam.py
- tests/integration/test_pack_skill_lifecycle.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/catalog.py
- src/specify_cli/skills/pack_skill_renderer.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/manifest.py
- src/specify_cli/skills/verifier.py
- src/specify_cli/runtime/agent_skills.py
- src/specify_cli/upgrade/migrations/m_2_0_11_install_skills.py
- src/specify_cli/upgrade/migrations/m_2_1_1_repair_skill_pack.py
- src/specify_cli/upgrade/migrations/m_3_0_3_globalize_skill_pack.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_spk_skill_pack.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- src/specify_cli/tool_surface/providers/plugin_bundle.py
- tests/specify_cli/skills/test_pack_skill_projection.py
- tests/specify_cli/skills/test_pack_skill_renderer.py
- tests/architectural/test_skill_catalog_seam.py
- tests/integration/test_pack_skill_lifecycle.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Catalog seam and project-root projection through the managed installer

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-009, FR-010, FR-011, FR-013, SC-001, SC-003, SC-007, SC-010, NFR-002, NFR-004 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP04 --agent claude`.

## Subtasks

### T015

RED FIRST: write tests/integration/test_pack_skill_lifecycle.py (SC-001) — temp project with claude+codex configured and a fixture org pack registered in charter_packs.org.packs with skill_namespace; activate skill → `.claude/skills/<ns>-<id>/SKILL.md` + `.agents/skills/<ns>-<id>/SKILL.md`; run upgrade-equivalent catalog callers with retire → still present; deactivate → removed; snapshot everything else byte-identical. Mark `@pytest.mark.regression` + issue #5193 while red; record the red run; un-mark once green.

### T016

Renderer (pack_skill_renderer.py): SKILL.md frontmatter (name, description, user-invocable per invocation) + generated preamble running `spec-kitty charter context --include <urn>` for every required URN; prompt form appends body; wrapper form instructs invoking the validated `builtin:spec-kitty.<cmd>` (validated against the command set; unknown target refused) or `cli:` spec-kitty argv. No bindings baked in; no `allowed-tools`.

### T017

Catalog seam catalog.py `resolve_project_skill_catalog(project_root)`: stages rendered pack skills under `.kittify/runtime/pack-skills/<name>/SKILL.md` and returns a merged registry (built-in `SkillRegistry.from_package()` ∪ staged) respecting `snapshot_catalog`. Manifest entries gain optional `origin` (default `builtin`), `source_ref`, `source_hash` (backward-compatible load). Installer: pack skills only to project skill roots of configured agents (AGENT_SKILL_CONFIG), never global; render-name collision fails before any write; an unowned existing dir with that name is preserved and reported; fix retire guard (`installer.py:739` `if retire and skills:`) so the last pack skill is retired even with an empty catalog.

### T018

Migrate every install/assess caller to the seam: verifier.py, runtime/agent_skills.py, init.py (out-of-map edit, justify), the four migrations, upgrade/assessment.py, managed_skills.py, plugin_bundle.py. Architectural test test_skill_catalog_seam.py: AST scan — no `SkillRegistry.from_package` call outside catalog.py/registry.py (allowlist must be empty or justified read-only listings).

### T019

`charter activate/deactivate skill` (cli/commands/charter/activate.py) re-runs projection after commit_plan; deactivate retires manifest-owned pack entries only. Unit tests for renderer, collisions (0 files written, NFR-002), unowned dir, wrapper validation, empty-catalog retire. Layer test green (charter imports no specify_cli).

## Amendments (post-tasks anti-laziness squad — binding)

- T015 ATDD must drive the real paths: `spec-kitty upgrade` (or each of the 4 migrations + verifier repair with retire=True), asserting presence after each; full-tree snapshot before activate vs after deactivate, excluding only `.kittify/runtime/pack-skills/` and the manifest.
- T017: staging counts as a write — run collision/duplicate checks BEFORE staging. NFR-002 snapshot covers all agent roots, staging dir and manifest, for both prepare-time duplicate and install-time collision. Assert nothing written under a fake HOME (never user-global).
- T016: unknown `builtin:spec-kitty.nope` refused with 0 writes; import the canonical command set (no copied literal); assert rendered body excludes the required procedure's text.
- T018: init.py has two `from_package()` sites (~:309, ~:1132) — migrate both; find managed_skills.py's real catalog source (registry_factory default) — migrate it, not vacuously. AST test: allowlist exact and reviewed (empty preferred), flags `SkillRegistry(` construction and `from_package` imports/attribute access.
- `cli/commands/charter/activate.py` is WP03-owned; add only the re-projection hook here (out-of-map edit, noted).

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

