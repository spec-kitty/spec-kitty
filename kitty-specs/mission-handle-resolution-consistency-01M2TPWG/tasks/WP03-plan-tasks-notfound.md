---
work_package_id: WP03
title: 'plan/tasks: truthful not-found for an unmatched handle'
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- FR-011
planning_base_branch: issue-4631-4682-mission-handle-resolution
merge_target_branch: issue-4631-4682-mission-handle-resolution
branch_strategy: Planning artifacts for this mission were generated on issue-4631-4682-mission-handle-resolution. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4631-4682-mission-handle-resolution unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
- T013
- T014
- T015
history:
- Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_mission_handle_not_found.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/mission_feature_resolution.py
- src/specify_cli/cli/commands/agent/mission_setup_plan.py
- src/specify_cli/cli/commands/agent/mission_check_prerequisites.py
- tests/specify_cli/cli/commands/agent/test_mission_handle_not_found.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role: implementer) via `/ad-hoc-profile-load` first.

## Objective

When `plan`/`tasks` receive an explicit `--mission <handle>` that matches nothing, emit
`Mission not found: <handle>` — NOT the misleading "N missions found, pass --mission to
disambiguate". Preserve the disambiguate message for the *different* no-handle multi-mission case.

## Context

- The disambiguate string is built by `_build_setup_plan_detection_error`
  (`agent/mission_feature_resolution.py:374-413`, message at `:404-407`). It was written for
  the *no-handle* auto-detect-failed case and ignores the explicit handle (it receives it as
  `mission_flag` metadata but does not branch on it).
- Both call-sites catch and overwrite the clean not-found that `_find_feature_directory`
  (`mission_feature_resolution.py:198-210`, `require_exists=True`, raises
  `FEATURE_CONTEXT_UNRESOLVED "Mission not found for handle '<h>'"`) already raises:
  - `mission_setup_plan.py:297-298` (plan)
  - `mission_check_prerequisites.py:636-651` → `:439` (tasks path)
- This is a **single chokepoint** — the fix lives almost entirely in
  `_build_setup_plan_detection_error`. The underlying resolver already fails *closed* (no
  silent success), so this is purely a mis-messaging bug.
- The no-handle multi-mission disambiguate path is pinned by
  `tests/specify_cli/cli/commands/agent/test_mission_feature_resolution.py:103-120` and
  `tests/agent/test_agent_feature.py:1006,1189` — those MUST stay green.
- Keep the existing `available_missions` **string-list** shape (do not switch to the rich
  dict shape — that would red the pinned tests; render unification is a follow-up).

## Subtasks

### T011 — Red tests
Create `tests/specify_cli/cli/commands/agent/test_mission_handle_not_found.py` (add
`pytestmark`). With ≥2 real missions: (a) `setup-plan`/`check-prerequisites --mission zznope`
→ output contains `Mission not found: zznope` AND does NOT contain "missions found, pass
--mission" or "to disambiguate"; (b) the no-handle (`--mission` omitted) multi-mission case
still emits the disambiguate message (regression guard, may duplicate the existing pinned test
intentionally). Initially (a) fails.

### T012 — Branch on explicit handle
In `_build_setup_plan_detection_error`, when a non-empty explicit handle was provided AND the
inbound error is the not-found (`FEATURE_CONTEXT_UNRESOLVED`), emit the canonical
`Mission not found: <handle>` (WP01 constant) and skip the disambiguate branch. When no handle
was given, keep the existing multi-mission disambiguate / no-missions payload unchanged.

### T013 — Verify both call-sites
Confirm both `mission_setup_plan.py` and `mission_check_prerequisites.py` surface the not-found
(they route through the one builder). Adjust only if a call-site swallows it before the builder.

### T014 — Preserve disambiguate
Ensure the no-handle multi-mission and zero-mission branches are byte-unchanged (run the pinned
tests).

### T015 — Green + gates
All T011 assertions pass; pinned tests green; `ruff`/`mypy` clean; functions ≤ complexity 15.

## Definition of Done
- Explicit unmatched handle → `Mission not found: <handle>` from plan and tasks.
- No-handle multi-mission disambiguate preserved.
- Blast radius: `PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/agent/ tests/tasks/ tests/agent/test_agent_feature.py -q`.

## Branch Strategy
Base/merge target `issue-4631-4682-mission-handle-resolution`; lane worktree from `lanes.json`.

## Reviewer guidance
Confirm the branch is on *explicit handle present* (not on mission count), the disambiguate
path is untouched for the no-handle case, and `available_missions` remains a string list.
