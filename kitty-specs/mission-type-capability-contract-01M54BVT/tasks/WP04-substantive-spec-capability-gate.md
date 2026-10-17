---
work_package_id: WP04
title: Site 4 — substantive-spec prerequisite keyed on requires_substantive_spec
dependencies:
- WP02
requirement_refs:
- FR-005
- NFR-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
phase: Phase 4 - Substantive-spec gate
history:
- timestamp: '2026-10-17T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py
tags: []
tracker_refs: []
---

# WP04 – Site 4: substantive-spec prerequisite on the capability

## Problem
`mission_check_prerequisites.py:429` gates the substantive-spec resume check on the literal set
`mission_type not in {"software-dev","research"}`, so a custom type with a real substantive-spec schema
cannot opt in, and the set is a maintenance hazard.

## Do
- **T011** — Replace the literal set with the `requires_substantive_spec` capability resolved on the mission type
  (from WP02, read via `charter.offering.api` / the resolved mission-type object). When the capability is true,
  run `is_substantive(spec_file, "spec", mission_type=mission_type)` as today; when false, committed-only suffices.
  Keep `is_substantive` itself in specify_cli (`_substantive`) — only the GATING predicate changes.
- **T012 [P]** — In `tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py`: RED-FIRST — a custom
  `requires_substantive_spec: true` type with a committed-but-thin spec FAILS the prerequisite; regression controls:
  `documentation` and `plan` committed specs still PASS (they stay `requires_substantive_spec=false`); `software-dev`
  thin spec still fails (parity).

## Constraints
- Must not flip documentation/plan to require FR rows (NFR-001). Capability-driven, not literal.
- One focused test + its regression controls (DIRECTIVE_041).

## Done when
`pytest tests/specify_cli/cli/commands/agent/test_mission_check_prerequisites.py tests/tasks/ -q` green; ruff/format/mypy clean.
