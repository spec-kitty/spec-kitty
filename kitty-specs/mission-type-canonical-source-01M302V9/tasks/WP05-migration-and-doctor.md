---
work_package_id: WP05
title: Consumer migration + doctor audit
dependencies:
- WP04
requirement_refs:
- FR-002
- FR-008
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
branch_strategy: Planning artifacts for this mission were generated on fix/mission-type-canonical-source-3831. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-type-canonical-source-3831 unless the human explicitly redirects the landing branch.
subtasks:
- T040
- T041
- T042
phase: Phase 5 - Migration
history:
- at: '2026-09-20T19:20:00Z'
  actor: system
  action: Prompt generated for mission-type-canonical-source
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- src/specify_cli/upgrade/migrations/m_mission_type_canonical_source.py
- tests/specify_cli/upgrade/test_mission_type_canonical_migration.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_mission_type_canonical_source.py
- tests/specify_cli/upgrade/test_mission_type_canonical_migration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Consumer migration + doctor audit

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load`.

## Objectives & Success Criteria
Migrate legacy consumer overrides to the canonical homes so nothing breaks when the resolver/tree retire. WP01 T004 (#4088) flips GREEN post-migration.

## Context & Constraints
- Depends on WP02 (slot) + WP04 (canonical loader). Use the config-aware migration helpers (`get_agent_dirs_for_project` pattern) — respect deletions, never `mkdir` blindly.
- Fail-closed on ambiguous/corrupt `mission.yaml`; audit every dropped field.

## Subtasks & Detailed Guidance
### Subtask T040 – Migration
- New migration: legacy `.kittify/missions/<type>/mission.yaml` `paths` → `path_conventions` slot; templates → template dirs; `.kittify/overrides/missions/<type>/` → `.kittify/doctrine/mission_types/<type>/`. Drop retired fields (`domain`/`version`/`validation`/`mcp_tools`/…) with an audit note; flat `required/optional` → unassigned/all-steps bucket (FR-005).
### Subtask T041 – doctor audit
- Surface the migration state in `spec-kitty doctor` (identity/doctrine audit family).
### Subtask T042 – Tests
- Migration unit/integration tests; flip WP01 T004 (#4088) GREEN using the WP01 override fixture.

## Test Strategy
- `.venv/bin/python -m pytest tests/specify_cli/upgrade/test_mission_type_canonical_migration.py -q`; re-run WP01 T004 (now GREEN).

## Risks & Mitigations
- Data loss on migration → fail-closed + audit; keep the legacy tree in place (deletion is #2661).

## Review Guidance
- Confirm migration is idempotent and audited; #4088 repro green only AFTER migration.

## Activity Log
- 2026-09-20T19:20:00Z – system – Prompt created.
