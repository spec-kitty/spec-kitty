---
work_package_id: WP02
title: Nightly timeout headroom (#5378)
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- FR-003
- FR-004
- NFR-002
planning_base_branch: issue-5367-nightly-census-and-timeout-headroom
merge_target_branch: issue-5367-nightly-census-and-timeout-headroom
branch_strategy: Planning artifacts for this mission were generated on issue-5367-nightly-census-and-timeout-headroom. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5367-nightly-census-and-timeout-headroom unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-census-and-timeout-headroom-01M3PM2S
base_commit: 4066173c35aca523cab0ac398d5b94077c1ecb06
created_at: '2026-09-29T13:11:57.247119+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 1 - Fix
history:
- at: '2026-09-29T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: .github/workflows/ci-nightly.yml
create_intent:
- tests/ci/test_nightly_timeout_headroom.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- .github/workflows/ci-nightly.yml
- tests/ci/test_nightly_timeout_headroom.py
- tests/architectural/_interpreter_shard_roster.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Nightly timeout headroom (#5378)

## ⚡ Do This First: Load Agent Profile

Load `implementer-ivan` (role: implementer) before parsing the rest of this prompt.

## Objective

See `tasks.md` → "Work Package WP02" for subtasks, independent test, and risks; root-cause evidence in `plan.md` and the phase-1 issue comments.

## Validation (targeted only — NO_FULL_HEAVY_SUITES_IN_MISSION)

- `pytest tests/ci/test_nightly_timeout_headroom.py tests/ci/test_nightly_exit_code_honesty.py tests/ci/test_interpreter_matrix_env_pinning.py tests/architectural/test_interpreter_shard_coverage.py tests/architectural/test_module_shard_registry.py`
- `ruff check` / `ruff format --check` on touched Python

## Activity Log

- 2026-09-29T13:30:00Z – system – Prompt generated via /spec-kitty.tasks
