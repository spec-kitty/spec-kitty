---
work_package_id: WP01
title: 'Fixtures & red-first repros (#3831 #4088)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
branch_strategy: Planning artifacts for this mission were generated on fix/mission-type-canonical-source-3831. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-type-canonical-source-3831 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-type-canonical-source-01M302V9
base_commit: 2a13aef93e1f857cd62e25417572d840add56968
created_at: '2026-09-20T19:33:33.414470+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fixtures
history:
- at: '2026-09-20T19:20:00Z'
  actor: system
  action: Prompt generated for mission-type-canonical-source
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/test_org_mission_type_resolution.py
create_intent:
- tests/specify_cli/test_org_mission_type_resolution.py
- tests/fixtures/mission_type_canonical/
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/test_org_mission_type_resolution.py
- tests/fixtures/mission_type_canonical/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Fixtures & red-first repros

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load` (the profile YAML, not the persona name) before implementing.

## Objectives & Success Criteria
Build the missing test scaffolding and the two failing repros that define done for the mission. Both repros MUST be RED at the end of this WP (they go green in WP04/WP05).

## Context & Constraints
- Spec/plan: `kitty-specs/mission-type-canonical-source-01M302V9/{spec.md,plan.md}` (read the "Consumer census & brownfield seam notes").
- No org-activated-custom-type consumer-project fixture nor `.kittify/overrides/missions/` fixture exists yet. Mine `tests/doctrine/{test_org_pack_subdir.py,drg/test_org_pack_config_resolve_existing_org_roots.py,test_service_org_layer.py}` for `doctrine.org.packs` config + `mission_types/<t>.yaml` authoring.
- Red-first per ADR 2026-07-17-1: `@pytest.mark.regression`, issue-pinned, RED through the pre-existing entry point.

## Subtasks & Detailed Guidance
### Subtask T001 – Org custom-type consumer-project fixture
- Build a fixture project: `.kittify/config.yaml` with `doctrine.org.packs`, an org pack exposing `mission_types/<type>.yaml`, and a feature `meta.json` recording that type — **no `.kittify/missions/`**.
### Subtask T002 – Project-override fixture
- Build fixtures for legacy `.kittify/overrides/missions/<type>/` and the canonical `.kittify/doctrine/mission_types/<type>/`.
### Subtask T003 – #3831 red repro (SC-001)
- Assert `get_mission_for_feature(feature_dir)` on T001 must resolve the custom type's identity/conventions/expected artifacts; it currently returns `Software Dev Kitty`. RED.
### Subtask T004 – #4088 red repro (SC-002)
- Assert the pre-migration `.kittify/overrides/missions/<type>/` override is honoured; it is ignored today. RED.

## Test Strategy
- New tests only; run just the new file (`.venv/bin/python -m pytest tests/specify_cli/test_org_mission_type_resolution.py -q`). Confirm both marked repros are RED for the documented reason.

## Risks & Mitigations
- Fixture drift → copy canonical org-pack shape from `tests/doctrine/`, never an older mission.

## Review Guidance
- Reviewer confirms repros fail for the RIGHT reason (org-blind loader / ignored override), not a fixture bug.

## Activity Log
- 2026-09-20T19:20:00Z – system – Prompt created.
