---
work_package_id: WP03
title: Decision-log module
dependencies:
- WP02
requirement_refs:
- FR-008
- FR-009
planning_base_branch: issue-2560-runtime-bridge-query-seam
merge_target_branch: issue-2560-runtime-bridge-query-seam
branch_strategy: Planning artifacts for this mission were generated on issue-2560-runtime-bridge-query-seam. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-2560-runtime-bridge-query-seam unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 2 - Extraction
history:
- at: '2026-10-06T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/runtime_bridge_decision_log.py
create_intent:
- src/runtime/next/runtime_bridge_decision_log.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- src/runtime/next/runtime_bridge_decision_log.py
- src/runtime/next/runtime_bridge.py
- src/runtime/next/runtime_bridge_io.py
- tests/runtime/test_runtime_bridge_query_*.py
- tests/runtime/test_bridge_decision_log_flush.py
- tests/runtime/test_decision_git_log_write_dir.py
- tests/runtime/test_bridge_decide_next.py
- tests/specify_cli/events/**
- tests/integration/**
- tests/architectural/test_no_write_side_rederivation.py
- tests/architectural/test_read_surface_placement_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Decision-log module

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

Move the coordination-aware decision-log wrapper into `src/runtime/next/runtime_bridge_decision_log.py` (plan D-2) so both the bridge's advance path and the future query module import it without a cycle or a deferred bridge import.

## Subtasks

### T010 — Create the decision-log module

Move verbatim: `DecisionGitLogUnavailable`, `_mission_routes_through_coordination`, `_is_owned_coordination_unavailable`, `_wrap_with_decision_git_log`. Imports identity + io at the top level; never the bridge, query, mapping or engine.

### T011 — io + bridge

- `runtime_bridge_io.resolve_commit_target`'s deferred import becomes `from runtime.next.runtime_bridge_decision_log import DecisionGitLogUnavailable` (still deferred: decision_log imports io). Update its docstring.
- Bridge: `from runtime.next import runtime_bridge_decision_log as _decision_log`; `_dn_bootstrap` / `answer_decision_via_runtime` call `_decision_log.<name>`; `DecisionGitLogUnavailable` is imported by name from the new module (the public name stays on the bridge as the same class). Drop now-unused imports.

### T012 — Tests and path-pinned gates

- Repoint every stale patch/import of the four names (squad: `_wrap_with_decision_git_log` patched in ~10 files, `_mission_routes_through_coordination` in ~5), applying the patch review rule.
- `tests/architectural/test_no_write_side_rederivation.py`: census pair → `src/runtime/next/runtime_bridge_decision_log.py::_wrap_with_decision_git_log`; in `_WRITE_DIR_CONSUMER_MODULES` replace the bridge with the new module (the bridge no longer calls `write_dir`; verify with grep).
- `tests/architectural/test_read_surface_placement_guard.py:328` docstring: reword the stale bridge `read_dir` claim.

### T013 — Flip

`_EXTRACTED["decision_log"] = True`.

## Definition of Done

- Decision-log rows pass; write-side gate file green; targeted surface green.
