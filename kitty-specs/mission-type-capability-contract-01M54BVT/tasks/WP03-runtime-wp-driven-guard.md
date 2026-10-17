---
work_package_id: WP03
title: Site 1 — WP-advance guard on wp_driven + cores Unregistered-skip fix
dependencies:
- WP01
requirement_refs:
- FR-003
- FR-004
- NFR-001
- SC-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
phase: Phase 3 - Runtime WP-advance guard
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/runtime/next/
create_intent:
- tests/runtime/test_wp_driven_guard.py
execution_mode: code_change
owned_files:
- src/runtime/next/runtime_bridge_io.py
- src/runtime/next/runtime_bridge_composition.py
- src/runtime/next/runtime_bridge_cores.py
tags: []
tracker_refs: []
---

# WP03 – Site 1: WP-advance guard on `wp_driven` + cores routing fix

## Problem
`runtime_bridge_composition.py:496` sets `wp_advance_ready` only for literal `software-dev`, and
`runtime_bridge_cores.evaluate_guards_strict` raises `UnregisteredMissionFamilyError` for a custom family
(caught at `composition.py` → neutral empty result). So a custom WP-driven family's implement/review
WP-advance guard is **silently skipped** and it can advance with work packages still pending.

## Do
- **T007** — `runtime_bridge_io.py`: add a `wp_driven` derivation that reads the frozen DAG
  (`run_dir/mission_template_frozen.yaml` via the existing `load_mission_template_file`, mirroring
  `mission_declares_analyze_step`) and applies `kernel.mission_runtime_shape.step_ids_declare_wp_iteration`.
  Carry the resulting bool as a plain fact on the `gather_artifact_presence` snapshot (the pure cores leaf must
  not read disk). Fail-closed to `False` on an unreadable template.
- **T008** — `runtime_bridge_composition.py:496`: set `wp_advance_ready` when `action in ("implement","review")`
  and the mission is `wp_driven` (use the snapshot/derivation, not the literal family).
- **T009** — `runtime_bridge_cores.py`: when the snapshot's `wp_driven` bool is true, route `implement`/`review`
  through `_evaluate_wp_iteration_guard` instead of raising `UnregisteredMissionFamilyError`. A non-wp_driven
  unregistered family keeps today's behaviour. Keep cores stdlib-only (consume the bool; do not import anything new).
- **T010 [P]** — `tests/runtime/test_wp_driven_guard.py`: RED-FIRST — a custom `wp_driven` mission at the
  implement board with a WP still pending must HOLD at the WP step (today it silently advances); controls:
  `software-dev` byte-identical, and `plan` resolves non-wp_driven (lone planning `review`, no `implement`).

## Constraints
- Byte-identical for all 4 built-ins (NFR-001); keep `tests/runtime/test_next_board_authority.py` / `test_runtime_seam.py` green.
- Key on `implement`, never `review`. One focused test per behaviour (DIRECTIVE_041).

## Done when
`pytest tests/runtime/ -q` green incl. the new red-first test; ruff/format/mypy clean.
