---
work_package_id: WP02
title: Capability facets (wp_driven, requires_substantive_spec) on the resolved mission type
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- NFR-002
- C-001
- C-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
phase: Phase 2 - Charter capability contract
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/charter/activation/mission_type_profiles.py
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/activation/mission_type_profiles.py
- src/charter/offering/missions/models.py
- src/charter/offering/api.py
- tests/charter/test_resolved_mission_type_context.py
tags: []
tracker_refs: []
---

# WP02 – Capability facets on the resolved mission type

## Goal
Expose two capabilities on `ResolvedMissionType` (`mission_type_profiles.py`) and the
`charter.offering.api` public surface, additively (NFR-002), as the single mission-type authority (C-001).

## Do
- **T004** — Add two fields/properties to `ResolvedMissionType`:
  - `wp_driven: bool` — derived at resolution via `kernel.mission_runtime_shape.step_ids_declare_wp_iteration`
    over the resolved action_sequence/step ids (`"implement" ∈ steps`). software-dev → true; research/documentation/plan → false.
  - `requires_substantive_spec: bool` — an AUTHORED capability read from the mission-type definition
    (`MissionType` model in `models.py` / governance-profile), with built-in defaults: software-dev = true,
    research = true, documentation = false, plan = false; a custom type with no declaration defaults to false.
    (It is a spec-CONTENT contract, not a DAG fact, and charter cannot import specify_cli's `is_substantive` — so it is
    declared/defaulted here, and the specify_cli gate (WP04) consumes it.) Add the optional field to the `MissionType`
    model so a pack CAN declare it; absence → the built-in default map / false.
- **T005** — Re-export both capabilities on `src/charter/offering/api.py` so consumers read them through the public surface.
- **T006 [P]** — In `tests/charter/test_resolved_mission_type_context.py`: assert each of the 4 built-ins resolves the
  expected `(wp_driven, requires_substantive_spec)` pair; a custom type declaring `requires_substantive_spec: true`
  resolves true; and the surface addition does not rename/remove an existing field (additive).

## Constraints
- Additive only; if the charter-offering contract carries an explicit version, note it — a required version bump is an
  operator decision (escalate the mechanics; don't drift the contract and docs).
- Reuse the kernel rule for `wp_driven` (no second derivation in charter).

## Done when
`pytest tests/charter/ tests/charter_offering/ -q` green; ruff/format/mypy clean; capabilities readable via `charter.offering.api`.
