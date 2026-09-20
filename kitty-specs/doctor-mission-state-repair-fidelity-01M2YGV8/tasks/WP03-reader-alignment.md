---
work_package_id: WP03
title: Reader alignment (durable fix)
dependencies: []
requirement_refs:
- FR-012
- NFR-001
planning_base_branch: fix/doctor-mission-state-repair-fidelity
merge_target_branch: fix/doctor-mission-state-repair-fidelity
branch_strategy: Planning artifacts for this mission were generated on fix/doctor-mission-state-repair-fidelity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/doctor-mission-state-repair-fidelity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-mission-state-repair-fidelity-01M2YGV8
base_commit: 0b8c0de8063c4cf8e74b5db0e4f7a463f6ca2438
created_at: '2026-09-20T05:24:39.859323+00:00'
subtasks:
- T014
- T015
- T016
- T017
phase: Phase 1 - Behavior preservation
history:
- at: '2026-09-20T05:01:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/bulk_edit/
create_intent:
- tests/specify_cli/test_change_mode_read_boundaries.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/implement.py
- src/specify_cli/bulk_edit/gate.py
- tests/agent/test_implement_command.py
- tests/specify_cli/bulk_edit/test_gate.py
- tests/specify_cli/test_change_mode_read_boundaries.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Reader alignment (durable fix)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `python-pedro` (implementer) before parsing the rest of this prompt.

---

## Objectives & Success Criteria

Close the whack-a-field class the post-plan squad found: make normalization genuinely behavior-preserving (NFR-001) by aligning every implicit `change_mode` presence-reader to the single canonical `== "bulk_edit"` check.

Done when:
- `implement.py:1340` is `if gate_result.change_mode == "bulk_edit": return` (was `is not None`) — so a legacy value and absence behave identically (both fall through to inference) (FR-012).
- `bulk_edit/gate.py:91-95` no longer propagates a raw legacy value: `GateResult.change_mode ∈ {"bulk_edit", None}` (a non-`bulk_edit` value collapses to `None`).
- A behavior-preservation test enumerates EVERY `change_mode` reader and asserts legacy-value ≡ absent at each (NFR-001/SC-006).

## Context & Constraints

- Post-plan squad [BLOCKER]: the gate returns the raw value and `implement.py:1340` `is not None` distinguishes legacy-value (skip inference) from absent (run inference → can `typer.Exit(1)`). This is why normalizing was NOT behavior-preserving. Operator chose the durable fold.
- Readers (from the scout): SAFE already — `gate.py:63` `_is_bulk_edit_mission` (`== "bulk_edit"`), `workflow_executor.py:1609` (`== "bulk_edit"`), `runtime_bridge.py:~921-932` (`.errors` only). UNSAFE — `implement.py:1340` (this WP).
- This WP is **file-disjoint from WP01/WP02** and runs in its own lane (may parallel WP01).
- Existing tests encode the old split — `test_implement_command.py:454` (`change_mode="code_change"` → skip) and `:678` (`None` → run), and `test_gate.py:88-92` (`result.change_mode == "standard"`). Updating these to the aligned contract is an **encoding update, not a regression** — document each.

## Subtasks

### T014 — Red: behavior-preservation enumeration test
Create `tests/specify_cli/test_change_mode_read_boundaries.py` (declare `pytestmark`). Enumerate each production reader of `change_mode` and assert the observable outcome is identical when the field holds a legacy value vs when it is absent. RED before the code change (fails at the `implement.py` boundary).

### T015 — Align `implement.py:1340`
Change `if gate_result.change_mode is not None:` → `if gate_result.change_mode == "bulk_edit":`. Add an inline rationale comment referencing the single-authority convention.

### T016 — Stop raw propagation in `gate.py`
In `gate.py:91-95`, return `change_mode="bulk_edit"` only for a bulk-edit mission, else `None` (do not pass the raw legacy value through `GateResult`). Pin the invariant `GateResult.change_mode ∈ {"bulk_edit", None}`.

### T017 — Update encoded tests
Update `test_implement_command.py:454/678` and `test_gate.py:88-92` to the aligned contract; in each, add a one-line comment noting this is the FR-012 alignment (legacy value now collapses to `None`/`!= bulk_edit` → inference runs), not a behavior regression.

## Branch Strategy
- Planning base / merge target: `fix/doctor-mission-state-repair-fidelity` (final PR → `main`). Own lane; worktree per `lanes.json`.

## Definition of Done
- T014–T017 green; the enumeration test proves legacy ≡ absent at every reader; ruff/mypy clean; new test file declares a marker (pytestmark gate); no new `__all__` export needed.

## Reviewer guidance
- Confirm the enumeration test actually covers `implement.py` (the counterexample), not only `gate.py:63`. Confirm `GateResult.change_mode` can no longer carry a raw legacy value. Confirm the test-encoding updates are justified, not green-washing.
