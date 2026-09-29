---
work_package_id: WP01
title: Census honesty (#5367)
dependencies: []
requirement_refs:
- C-003
- FR-001
- FR-002
- NFR-001
- NFR-002
planning_base_branch: issue-5367-nightly-census-and-timeout-headroom
merge_target_branch: issue-5367-nightly-census-and-timeout-headroom
branch_strategy: Planning artifacts for this mission were generated on issue-5367-nightly-census-and-timeout-headroom. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5367-nightly-census-and-timeout-headroom unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-census-and-timeout-headroom-01M3PM2S
base_commit: 4066173c35aca523cab0ac398d5b94077c1ecb06
created_at: '2026-09-29T13:11:24.299046+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fix
history:
- at: '2026-09-29T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: packs/built-in/toolguides/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- packs/built-in/toolguides/java-supply-chain.toolguide.yaml
- packs/built-in/toolguides/javascript-supply-chain.toolguide.yaml
- packs/built-in/toolguides/python-supply-chain.toolguide.yaml
- packs/built-in/pack-manifest.yaml
- tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Census honesty (#5367)

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (role: implementer) before parsing the rest of this prompt.

## Objective

See `tasks.md` → "Work Package WP01" for subtasks, independent test, and risks; root-cause evidence in `plan.md` and the phase-1 issue comments.

## Validation (targeted only — NO_FULL_HEAVY_SUITES_IN_MISSION)

- `pytest tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py tests/doctrine/test_supply_chain_single_owner.py`
- `spec-kitty doctrine regenerate-graph --check` (fresh)
- `ruff check` / `ruff format --check` on touched Python

## Activity Log

- 2026-09-29T13:30:00Z – system – Prompt generated via /spec-kitty.tasks
