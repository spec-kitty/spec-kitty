---
work_package_id: WP01
title: Shared planning checkout verdict
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
- SC-002
planning_base_branch: fix/7594-shared-checkout-verdict
merge_target_branch: fix/7594-shared-checkout-verdict
branch_strategy: Planning artifacts for this mission were generated on fix/7594-shared-checkout-verdict. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7594-shared-checkout-verdict unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Slice 1 (#7594)
history:
- at: '2026-11-13T18:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_planning_checkout_verdict.py
- docs/changelog/unreleased/7594-planning-checkout-verdict.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_branch_context.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/specify_cli/cli/commands/agent/test_planning_checkout_verdict.py
- tests/specify_cli/cli/commands/agent/test_setup_plan_branch_match.py
- tests/fixtures/setup_plan_pre_mission_replay.py
- docs/changelog/unreleased/7594-planning-checkout-verdict.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Shared planning checkout verdict

## Objectives & Success Criteria

- setup-plan and check-prerequisites report identical `current_branch`, `target_branch`, `expected_checkout_branch` and `branch_matches_target` for a default Mission before and after settlement (SC-001).
- Owned, FR-006 lane-worktree and protected-mint pins stay green (SC-002).

## Context & Constraints

- Design: `plan.md` § Design. Grounding and gates: `research.md`.
- C-001: consume `placement_seam(...).write_target(MissionArtifactKind.PRIMARY_METADATA).ref`; never re-derive placement.
- C-002: no commit-destination change. setup-plan keeps its `target_branch` argument to the commit helpers.
- Red-first: T001 is its own commit before any fix commit.

## Subtasks & Detailed Guidance

### T001 – Red acceptance test
`tests/specify_cli/cli/commands/agent/test_planning_checkout_verdict.py` drives the real commands on real default Missions (before and after `finalize-tasks`, from the root checkout and the coordination worktree), plus an explicit-topology control.

### T002 – Shared helper
`resolve_planning_checkout_verdict(repo_root, mission_slug, *, invoking_root, owned, fallback_branch)` returns a frozen `PlanningCheckoutVerdict`. If the seam cannot resolve, it degrades to a silent match.

### T003 / T004 – Consumers
Both commands pass the verdict into `_inject_branch_contract`. check-prerequisites resolves the invocation identity once at the entry point.

### T005 – Tests and changelog
Re-point the patches of the retired helpers. Add `docs/changelog/unreleased/7594-planning-checkout-verdict.fixed.md`.

## Validation

- `pytest tests/specify_cli/cli/commands/agent/test_planning_checkout_verdict.py test_setup_plan_branch_match.py test_mission_check_prerequisites.py test_mission_branch_context.py test_setup_plan_read_surface.py test_mission_setup_plan_phases.py` and the owned-checkout pins
- Gates: `test_no_write_side_rederivation.py`, `test_mission_resolver_walker_gate.py`, `test_layer_rules.py`, `test_no_dead_symbols.py`, `test_status_read_single_door.py`, `test_coord_read_residuals_closeout.py`, `test_commit_recipe_strings.py`, `test_no_legacy_terminology.py`
- `make test-fast`, ruff, ruff format, mypy
