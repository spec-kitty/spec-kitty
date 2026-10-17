---
work_package_id: WP01
title: Shared runtime-shape parser + wp_driven rule in kernel
dependencies: []
requirement_refs:
- FR-006
- C-004
- NFR-003
- SC-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Kernel single authority
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/charter/offering/missions/mission_step_repository.py
create_intent:
- src/kernel/mission_runtime_shape.py
- tests/kernel/test_mission_runtime_shape.py
execution_mode: code_change
owned_files:
- src/charter/offering/missions/mission_step_repository.py
- tests/charter_offering/missions/test_mission_type_repository.py
tags: []
tracker_refs: []
---

# WP01 – Shared runtime-shape parser + `wp_driven` rule in `kernel`

## Goal
Single-source the runtime-shape step-id reader and the `wp_driven` derivation rule in `kernel`
(the only layer both `charter` and `runtime` import), replacing slice-1's charter-local duplicate.

## Do
- **T001** — New `src/kernel/mission_runtime_shape.py`:
  - `read_runtime_shape_step_ids(path: Path) -> list[str]` — port the EXACT fail-closed contract from
    `charter.offering.missions.mission_step_repository._runtime_shape_step_ids` (merged in #6317): parse the flat
    `steps:` list via a safe YAML load; return `[]` if unreadable, non-dict root, non-list `steps`, or ANY entry
    that is not a mapping with non-empty `id` AND non-empty `title`; else the ordered ids.
  - `step_ids_declare_wp_iteration(step_ids: Iterable[str]) -> bool` — `return "implement" in set(step_ids)`
    (use the canonical implement step id; do NOT key on `review`, so `plan` stays non-WP-driven).
  - Pure: stdlib + kernel's existing yaml helper only. No imports from charter/runtime/specify_cli.
- **T002** — In `mission_step_repository.py`: delete the local `_runtime_shape_step_ids`; make
  `resolve_runtime_shape_steps` call `kernel.mission_runtime_shape.read_runtime_shape_step_ids`. No behaviour change.
- **T003 [P]** — `tests/kernel/test_mission_runtime_shape.py`: fail-closed cases (empty/malformed/missing-id/missing-title → `[]`)
  + the wp_driven rule (implement present/absent). RE-POINT the existing parity test
  `test_charter_reader_agrees_with_runtime_loader_on_step_ids` in `tests/charter_offering/missions/test_mission_type_repository.py`
  to assert `kernel` reader == runtime `load_mission_template_file` step ids (kernel↔runtime now).

## Constraints
- Byte-identical charter behaviour (shim only). Runtime's richer `load_mission_template_file` is NOT replaced.
- Red-first where it earns it (DIRECTIVE_041): the fail-closed kernel cases are the witnesses; don't duplicate slice-1's charter tests — the parity test moves, it isn't cloned.

## Done when
`pytest tests/kernel/ tests/charter_offering/missions/ -q` green; ruff/format/mypy clean on touched files; the duplicate parser is gone.
