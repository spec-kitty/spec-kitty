---
work_package_id: WP04
title: Query module and public re-exports
dependencies:
- WP03
requirement_refs:
- FR-001
- FR-003
- FR-005
- FR-006
- FR-009
- NFR-001
- SC-001
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T014
- T015
- T016
- T017
- T018
phase: Phase 2 - Extraction
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_query.py
create_intent:
- src/runtime/next/runtime_bridge_query.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge_query.py
- src/runtime/next/runtime_bridge.py
- tests/runtime/test_runtime_bridge_query_*.py
- tests/next/**
- tests/runtime/**
- tests/specify_cli/next/**
- tests/specify_cli/cli/commands/**
- tests/specify_cli/orchestrator_api/**
- tests/integration/**
- tests/unit/mission_loader/**
- tests/architectural/test_runtime_emitter_seam.py
- tests/architectural/test_coord_read_residuals_closeout.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Query module and public re-exports

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

Move the read path into `src/runtime/next/runtime_bridge_query.py`; the bridge re-exports `query_current_state`, `answer_decision_via_runtime`, `QueryModeValidationError`, `MissionNotFoundError` (and `DecisionGitLogUnavailable` from decision_log) as plain imports.

## Subtasks

### T014 — Create the query module

Move verbatim: `_READ_PATH_ERROR_CODES`, `_is_read_path_error`, `QueryModeValidationError`, `MissionNotFoundError`, the four `_build_*query*` builders, `query_current_state`, `_query_resolve_mission_context`, `_query_read_runtime_plan`, `_query_dispatch_decision`, `answer_decision_via_runtime`. Imports mapping, decision_log, engine, io, cores; never the bridge.

### T015 — Re-exports + imports

Bridge top level: `from runtime.next.runtime_bridge_query import MissionNotFoundError, QueryModeValidationError, answer_decision_via_runtime, query_current_state`. `__all__` unchanged. Drop every import the bridge no longer uses (expected per squad A-9: `_find_first_wp_by_lane`, `get_all_wp_snapshots`, `has_operator_provenance`, `load_mission_template_file`, `runtime_provide_decision_answer`, `ActorIdentity`, `MissionRuntimeError`, `shutil`, `KITTY_SPECS_DIR`, `routes_through_coordination` — whatever ruff F401 confirms).

### T016 — Repoint tests

Loud failures first (AttributeError), then the go-silent names (squad T-3): `tests/next/test_query_mode_unit.py` `_compute_wp_progress` / `get_mission_type` patches; `tests/next/test_runtime_bridge_unit.py:622/626/632` (`get_mission_type`, `runtime_emitter_for_mission`, `runtime_provide_decision_answer`) and its negative `emitter_calls == []` assertion, which must be paired with a positive control that proves the emitter patch is live. Patches of the public names on the bridge (`runtime_bridge.query_current_state`) stay valid only for callers that read them through the bridge (the CLI); review each by call path.

### T017 — Gates following the move

- `tests/architectural/test_runtime_emitter_seam.py` S8: `_dn_bootstrap` is checked in the bridge, `answer_decision_via_runtime` in the query module; both files must import `runtime_emitter_for_mission` by name and never construct `RuntimeEventEmitter`.
- `tests/architectural/test_coord_read_residuals_closeout.py:541,549`: match the `runtime_bridge` file prefix, not the `runtime_bridge.py` substring; update stale line-number prose.

### T018 — Flip

`_EXTRACTED["query"] = True`; the layout gate is now fully green with no xfail mark left (remove the mechanism if no row remains marked).

## Definition of Done

- Layout gate fully green; `runtime_bridge.py` ≤ 2,575 LOC; targeted surface green.
