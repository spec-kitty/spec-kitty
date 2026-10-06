---
work_package_id: WP02
title: Decision-mapping module and engine back-edge
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-004
- FR-005
- FR-006
- SC-002
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
- T008
- T009
phase: Phase 2 - Extraction
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_decision_mapping.py
create_intent:
- src/runtime/next/runtime_bridge_decision_mapping.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge_decision_mapping.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_engine.py
- tests/runtime/test_runtime_bridge_query_*.py
- tests/runtime/test_bridge_decision_builder.py
- tests/runtime/test_bridge_decide_next.py
- tests/runtime/test_bridge_engine.py
- tests/next/**
- tests/runtime/next/**
- tests/specify_cli/next/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Decision-mapping module and engine back-edge

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission runtime-bridge-query-seam-01M490EQ`) or the Activity Log below. Address all feedback before the work is complete.

## Branch Strategy

- Planning/base branch: `issue-2560-runtime-bridge-query-seam` (stacked on `issue-2561-retire-runtime-bridge-delegates`, PR #5822).
- Final merge target: `issue-2560-runtime-bridge-query-seam`.
- Topology `single_branch`: the WP runs in the repository root checkout; there is no lane worktree.

## Shared rules (all WPs)

- Behaviour-preserving (spec C-001). The one accepted delta is logger names for moved code (plan "Accepted deltas").
- Source changes stay inside `src/runtime/next/` (C-002). No forwarding delegate or self-alias in `runtime_bridge.py` (C-003). New modules follow the `runtime_bridge_<name>.py` convention.
- Moved code is moved **verbatim** (cut/paste plus import fix-ups only). Do not "improve" moved bodies.
- The bridge calls a moved name as `<alias>.<name>` (`_mapping`, `_decision_log`, `_query`). Drop every import the bridge no longer uses (ruff F401), so a stale `runtime_bridge.<name>` patch raises AttributeError.
- **Patch review rule (squad T-1/T-2):** when a test's import or patch of a moved name is repointed, review every other patch in the same test and `with` block by call path. A patch that steered moved code via the bridge must target the owning module now, and the test must assert its fake ran (`.assert_called()`, a call counter, or an observable effect only the fake produces).
- Complexity ≤ 15, no new `noqa`/`type: ignore`. `ruff check`, `ruff format --check --force-exclude <changed files>`, mypy over `src/runtime/next/` adds no error beyond the 21 on the base.

## Objective

Create `src/runtime/next/runtime_bridge_decision_mapping.py` holding the decision mapping shared by the advance path, the engine adapter and (later) the query module; remove the engine's deferred `_rb` import.

## Subtasks

### T005 — Create the mapping module

Move verbatim (plan D-1): `_prompt_exists`, `_materialize_decision`, `TASKS_GLOB`, `_WP_ITERATION_STEPS`, `_is_wp_iteration_step`, `_has_claimable_planned_wp`, `_finalized_task_board_override_step`, `_reduced_wp_lane`, `_count_wp_endings`, `_MERGED_MISSION_DONE_REASON`, `_merged_mission_short_circuit`, `_WpIterationResolution`, the WP-board family (`_WpBoardAction` … `_resolve_wp_board_action`), `_wp_iteration_action_and_state`, `_build_wp_iteration_decision`, `_build_decision_required_prompt_file`, `_map_wp_step_decision`, `_map_non_wp_step_decision`, `_map_runtime_decision`. Module docstring states ownership and the import rule (imports cores / `runtime.next.decision` / below; never the bridge, query, engine, decision_log, composition).

### T006 — Bridge uses `_mapping`

`from runtime.next import runtime_bridge_decision_mapping as _mapping`; every bridge call site of a moved name becomes `_mapping.<name>` (incl. `_should_advance_wp_step` → `_mapping._wp_task_surface_error`, `_mapping.TASKS_GLOB`). Drop imports the bridge no longer uses.

### T007 — Engine back-edge

`runtime_bridge_engine.py` imports the mapping module at the top level and calls `_mapping._is_wp_iteration_step` / `_mapping._map_runtime_decision`; delete the deferred `from runtime.next import runtime_bridge as _rb`. Update the engine docstring paragraph that explains the back-edge.

### T008 — Repoint tests

Run the targeted surface; every AttributeError from a stale `runtime_bridge.<moved name>` patch/import is repointed at `runtime_bridge_decision_mapping`, applying the patch review rule to every sibling patch in the test. Known sites (squad): `tests/next/test_runtime_bridge_blocked_paths.py` (imports + `_state_to_action`/`_build_prompt_or_error` patches), `tests/next/test_prompt_file_invariant.py`, `tests/runtime/test_bridge_decide_next.py` (`_is_wp_iteration_step`, `_wp_iteration_action_and_state`, `_map_runtime_decision`), and the characterisation `_owner` table.

### T009 — Source-scan gates + flip

`tests/runtime/test_bridge_decision_builder.py`: the bare-`_materialize_decision` call count and the "zero raw `Decision(...)`" scan read the bridge **plus** the three seam modules that exist (missing files skipped until created). Set `_EXTRACTED["mapping"] = True` in the layout gate.

## Definition of Done

- Mapping rows of the layout gate pass; no strict-xfail row unexpectedly passes.
- Targeted surface green except the base's known environmental reds.
