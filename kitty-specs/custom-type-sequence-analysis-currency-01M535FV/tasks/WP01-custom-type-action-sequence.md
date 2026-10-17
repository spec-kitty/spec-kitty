---
work_package_id: WP01
title: Custom-type action_sequence resolves from the runtime-DAG shape
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-001
- C-003
- SC-001
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Charter projection
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/charter/offering/missions/
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/offering/missions/mission_type_repository.py
- src/charter/offering/missions/mission_step_repository.py
- tests/charter_offering/missions/test_mission_type_repository.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – Custom-type action_sequence resolves from the runtime-DAG shape

## Problem

spec-kitty has two disjoint step authorities. Charter's `action_sequence` projection
(`project_action_sequence` ← `MissionStepRepository.resolve_all_for_mission_type` ←
`_inject_projected_fields`, `src/charter/offering/missions/mission_type_repository.py:274-284`)
reads ONLY the dir-per-step shape `mission-steps/<type>/<step>/step.yaml`. Org packs
(cave-kitty / qa) ship ONLY the runtime-DAG shape `missions/<type>/mission-runtime.yaml`
(a flat `steps:` list), read only by `runtime.next`. So an activated org-pack-shape custom
type projects an empty sequence and fails with `MissionTypeEmptyActionSequenceError`
(`src/charter/activation/mission_type_profiles.py:285-313`).

## Goal

Teach charter's single projection producer a charter-local fallback reader of the runtime-DAG
step list, so an activated custom type resolves its full ordered `action_sequence`. Reuse the
existing projection; introduce no new mission-type resolver (NFR-002, C-001).

## Constraints (binding)

- **Charter MUST NOT import `runtime`** (enforced layer chain `kernel <- charter <- {glossary,
  runtime, mission_runtime} <- specify_cli`). The reader is a charter-local plain-YAML parse of
  `id` + declared order only, using the module's thread-local `YAML(typ="safe")`.
- **Fail-closed preserved**: an empty or malformed runtime must still yield an empty projection →
  `None` → `MissionTypeEmptyActionSequenceError`. Do NOT weaken that.
- **Built-ins byte-identical** (NFR-001): built-in types have a non-empty dir-per-step projection,
  so the fallback must never fire for them. Assert this.
- No packaging/gate changes (C-003).

## Subtasks

- **T001** — New charter-local reader in `charter.offering.missions` (helper in
  `mission_step_repository.py` or a sibling module), e.g.
  `resolve_runtime_shape_steps(mission_type_id, pack_context) -> list[MissionStep]`, reading
  `<pack_root>/missions/<type>/mission-runtime.yaml` (and the project-tier equivalent) from the
  `pack_context` already in hand. Synthesize `MissionStep` (`models.py`) with
  `in_action_sequence=True`, `sequence_index=<enumerate position>`.
- **T002** — In `_inject_projected_fields` (`mission_type_repository.py:274-284`):
  `projected_sequence = project_action_sequence(steps) or project_action_sequence(resolve_runtime_shape_steps(...))`;
  keep the existing `or raw.get("action_sequence")` final fallback (`:283`) and the empty→`None` path.
- **T003 [P]** — Red-first tests in `tests/charter_offering/missions/` (e.g.
  `test_mission_type_repository.py`): a custom type shipping only `mission-runtime.yaml`
  (steps `[discovery, specify, plan, tasks, analyze, implement, review, accept]`) + a bare
  `mission_types/<type>.yaml` resolves `action_sequence` equal to that list in order
  (FR-001 positive control); an empty/malformed runtime still raises
  `MissionTypeEmptyActionSequenceError` (FR-002, same-fixture paired control); a built-in type's
  resolved sequence is unchanged (NFR-001).

## Test economy (DIRECTIVE_041 / development-assist-test-cleanup)

Add a test only where it guards real behaviour through the existing entry point with realistic
data and fails on a real regression. Pair the positive control (FR-001) with the fail-closed
control (FR-002) on the same fixture (non-vacuity). No shape pins, no inert self-compares, no
duplicate of an existing projection assertion. Prefer strengthening an existing projection test
over a new function where it fits. Provide a table: test → fold → regression caught → existing coverage.

## Definition of done

- `spec-kitty mission-type list` (and `resolve_mission_type_context`) resolves the custom type's
  full ordered sequence with no empty-sequence error.
- Fail-closed and built-in parity assertions green. `ruff`/`mypy` clean, complexity ≤ 15.
