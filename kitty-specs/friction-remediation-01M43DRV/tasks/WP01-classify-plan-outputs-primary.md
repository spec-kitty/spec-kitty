---
work_package_id: WP01
title: Classify quickstart.md and contracts/** as PRIMARY
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-5552-friction-remediation
merge_target_branch: issue-5552-friction-remediation
branch_strategy: Planning artifacts for this mission were generated on issue-5552-friction-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5552-friction-remediation unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-10-04T12:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- tests/consolidation/test_projection_excludes_plan_outputs.py
execution_mode: code_change
owned_files:
- src/mission_runtime/artifacts.py
- src/specify_cli/coordination/commit_router.py
- tests/mission_runtime/test_artifact_partition.py
- tests/consolidation/test_projection_excludes_plan_outputs.py
- tests/architectural/test_write_surface_placement_guard.py
- tests/architectural/test_merge_reconciliation_class_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5552'
---
# Work Package Prompt: WP01 – Classify quickstart.md and contracts/** as PRIMARY

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (`/ad-hoc-profile-load python-pedro`) and follow it.

Mission: `friction-remediation-01M43DRV`. Read `../spec.md`, `../plan.md` and `../research/code-grounding.md` §1 first.

## Objective

Make `mission_runtime.kind_for_mission_file` classify:
- `kitty-specs/<m>/quickstart.md` as `CHECKLIST`. This agrees with `acceptance/__init__.py::_accept_planning_artifact_kinds`.
- `kitty-specs/<m>/contracts/**` as a NEW PRIMARY-partition kind, `CONTRACT`.

Squash consolidate's `bookkeeping_projection._post_checkpoint_mission_paths` then excludes both from projection, which ends the #5552 false REFUSE.

## Subtasks

- **T001 (RED, separate commit)**:
  - Add `tests/consolidation/test_projection_excludes_plan_outputs.py`. Build a git fixture with a checkpoint commit, then a coordination commit that adds `kitty-specs/<m>/quickstart.md`, `contracts/a.md`, `contracts/sub/b.yaml` and `traces/approach.md`.
  - Assert `_post_checkpoint_mission_paths` returns only the traces path. This is the positive control on the same fixture.
  - Add classifier unit tests to `tests/mission_runtime/test_artifact_partition.py`.
  - Commit red.
- **T002**: In `src/mission_runtime/artifacts.py`:
  - add the enum member `CONTRACT` with a rationale comment;
  - add `"quickstart.md": CHECKLIST` to `_MISSION_FILE_KIND_BY_BASENAME`;
  - add `"contracts": CONTRACT` to `_COORD_RESIDUE_DIRS`;
  - add `CONTRACT` to `_PRIMARY_ARTIFACT_KINDS`.
- **T003**: Add `CONTRACT` to `commit_router._PRE_TASKS_ARTIFACT_KINDS`.
- **T004**: Re-point the gates:
  - `test_write_surface_placement_guard.py` `primary_kinds` += CONTRACT;
  - `test_merge_reconciliation_class_guard.py`: `_NON_DIVERGENT_CANONICAL_ARTIFACTS` += quickstart.md, and `_NON_DIVERGENT_COORD_RESIDUE_DIRS` += contracts.
- **T005**: Run the callers' tests (the list is in the grounding note) and the named gates.

## Definition of Done

- The T001 test was red before T002 and is green after.
- The placement guard, `test_mission_runtime_surface.py` and `test_merge_reconciliation_class_guard.py` are green.
- The `kind_for_mission_file` callers' tests are green.
- ruff, format and mypy are clean on the changed files.

## Reviewer guidance

- Verify write placement is unchanged: `artifact_home_for(CONTRACT)` resolves PRIMARY.
- Check that no allowlist grew.
