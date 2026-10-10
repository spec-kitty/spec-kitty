---
work_package_id: WP03
title: Owned requirement mapping
dependencies:
- WP02
requirement_refs:
- C-001
- C-003
- FR-003
- FR-008
- NFR-002
- NFR-003
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
- T013
phase: Phase 3 - Requirement mapping
history:
- at: '2026-10-10T06:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_map_requirements.py
create_intent:
- tests/integration/test_owned_map_requirements.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/tasks.py
- src/specify_cli/cli/commands/agent/tasks_map_requirements.py
- src/specify_cli/status/emit.py
- tests/integration/test_owned_map_requirements.py
- tests/specify_cli/cli/commands/agent/test_map_requirements_commit_result_json.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#5878'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile with the `/spk-charter-profile-load` skill (profile: `python-pedro`, role: implementer). Then continue.

# Work Package Prompt: WP03 – Owned requirement mapping (#5878)

## Objectives & Success Criteria

- `agent tasks map-requirements` resolves an owned single_branch mission, reads/writes its WP + spec surface from the owned checkout, and commits on the owned write branch; a stale primary copy is left untouched (FR-003).
- `emit_inner_state_changed` refuses a `feature_dir`/`mission_slug` that does not match the owned fact; non-owned behaviour and all refusals preserved (FR-008). **No `core/paths.py` change** (C-001).
- Every new branch/helper has a focused test (NFR-003); `ruff` + `mypy --strict` clean (NFR-002).

## Context & Constraints

- Grounding + provenance: `../research.md` (row #5878), `../plan.md` IC-03.
- Repair branch to land-and-verify: `codex/5878-owned-requirement-mapping`, fix `885833015` + test `03c71230f`. **Adopt-as-is** — source hunks apply 3-way clean against origin/main; `core/paths.py` is NOT edited.
- Root cause (origin/main): `map_requirements` (tasks.py) exposes no `--owned-checkout`; `tasks_map_requirements._mr_resolve_context` folds via `locate_project_root` / `_ensure_target_branch_checked_out` (→ `get_main_repo_root`); read dirs / `MissionHandle` / `placement_seam` all keyed to the folded root; `status/emit.py::emit_inner_state_changed` canonicalizes `feature_dir` with no owned authority.
- Model (sibling in same file): `agent tasks status` takes `owned_claim` via `_resolve_task_owned`; `agent_tasks_ports._owned_kwargs`/`_seam_for` → `placement_seam(..., owned=)` + `MissionHandle.owned`.
- Post-merge caution: `main` added a `mission_write_lock` + `locked_update_frontmatter` refactor in this file; confirm it composes with the owned-pinned `primary_dir` after the merge (the lock keys on the owned-resolved primary dir).
- Charter: C-001; C-003 ATDD red-first; DIRECTIVE_024 locality.

## Branch Strategy

- **Planning base branch**: main · **Merge target branch**: main. Runs in the write checkout.

## Subtasks & Detailed Guidance

### Subtask T009 – ATDD: port the owned requirement-mapping reproduction (RED first)

- **Steps**: Port `tests/integration/test_owned_map_requirements.py` (from `03c71230f`): `test_mapping_stays_owned` (explicit × auto), `test_tracker_reference_ignores_stale_primary`, `test_tracker_only_preserves_refs`, `test_invalid_owned_claim_refused_before_writes`, `test_owned_annotation_refuses_foreign_mission`. Also port the `monkeypatch.chdir` fixture tweak in `tests/specify_cli/cli/commands/agent/test_map_requirements_commit_result_json.py`.
- **Validation**: RED on base (`MISSION_NOT_FOUND`). Record it.

### Subtask T010 – Add `--owned-checkout` to map-requirements and mint once

- **Steps**: In `tasks.py`, add `owned_checkout: OwnedCheckoutOption` to `map_requirements`, mint `owned = _resolve_task_owned(owned_checkout, mission, …)`, pass `owned=owned` into `_do_map_requirements`.
- **Files**: `src/specify_cli/cli/commands/agent/tasks.py`.

### Subtask T011 – Thread owned through the mapping state and placement

- **Steps**: Apply `885833015` to `tasks_map_requirements.py`: add `owned` to `_MapReqState` + `_do_map_requirements`; in `_mr_resolve_context` prefer `owned.repository_root`/`mission_slug`/`owned_root`/`write_branch` over the fold, and use `placement_seam(…, owned=…).write_target(WORK_PACKAGE_TASK)` + `ProtectionPolicy.resolve_for_owned(owned)`; in `_mr_resolve_read_dirs` resolve `feature_dir`/`tasks_dir` via `placement_seam(…, owned=…).read_dir(...)` + owned `MissionHandle`; in `_mr_write_frontmatter` pass `owned=` to the annotation emit; in `_mr_auto_commit` extend written files with owned status files + owned `MissionHandle` + `resolve_for_owned`; in `_mr_emit_output` add `stale_copy_payload` / `echo_stale_copy_warning`.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_map_requirements.py`.

### Subtask T012 – Owned guard in emit_inner_state_changed

- **Steps**: Add an `owned` param to `status/emit.py::emit_inner_state_changed`; when owned, REFUSE a `feature_dir`/`mission_slug` mismatch vs `owned.mission_dir`/`owned.mission_slug` (`ValueError`), else pin `feature_dir = owned.mission_dir`, `repo_root = owned.owned_root`. Non-owned path unchanged.
- **Files**: `src/specify_cli/status/emit.py`.

### Subtask T013 – Validate green

- **Steps**: Run `tests/integration/test_owned_map_requirements.py` + the map-requirements test modules under `tests/specify_cli/cli/commands/agent/` + `tests/status/` (owns emit). format-check + ruff + mypy on changed files. Green.

## Definition of Done

- Repro RED→GREEN; stale primary untouched; foreign-mission annotation refused; non-owned unchanged; `core/paths.py` untouched; lint/type clean; `mission_write_lock` composition confirmed by a green reworked integration run.

## Reviewer Guidance

- Confirm no `core/paths.py` edit; confirm every read/write dir routes through `placement_seam(..., owned=)`; confirm the emit guard raises before any write.
