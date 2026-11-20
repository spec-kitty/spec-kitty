---
work_package_id: WP01
title: One claim sidecar and one planned release
dependencies: []
requirement_refs:
- FR-004
- FR-006
planning_base_branch: issue-5781-api-claim-accept-readiness
merge_target_branch: issue-5781-api-claim-accept-readiness
branch_strategy: Planning artifacts for this mission were generated on issue-5781-api-claim-accept-readiness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5781-api-claim-accept-readiness unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Claim parity
history:
- at: '2026-11-20T19:40:00Z'
  actor: claude::python-pedro
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- src/specify_cli/status/claim_release.py
- tests/orchestrator_api/test_api_claim_sidecar_5781.py
- tests/status/test_claim_release.py
- tests/consolidation/test_done_bookkeeping_reviewer_fallback.py
execution_mode: code_change
owned_files:
- src/specify_cli/status/emit.py
- src/specify_cli/status/claim_release.py
- src/specify_cli/status/__init__.py
- src/specify_cli/orchestrator_api/wp_lifecycle.py
- src/specify_cli/cli/commands/agent/status.py
- src/specify_cli/cli/commands/agent/tasks_move_task_hops.py
- src/specify_cli/consolidation/done_bookkeeping.py
- tests/orchestrator_api/test_api_claim_sidecar_5781.py
- tests/status/test_claim_release.py
- tests/consolidation/test_done_bookkeeping_reviewer_fallback.py
- tests/agent/test_orchestrator_commands_integration.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# WP01 – One claim sidecar and one planned release

Load the `python-pedro` profile first.

## Objective

Every `planned -> claimed` write records `agent` through the one builder in `status/emit.py`: host claims, `orchestrator-api start-implementation`, `orchestrator-api transition --to claimed`, and `agent status emit --to claimed`. Every move into `planned` releases the runtime claim through one helper in `status/claim_release.py` (#7644). See `../plan.md` IC-01/IC-02 and `../research.md` D-04, D-05, D-08.

## Red first (separate commit, before any implementation)

- `tests/orchestrator_api/test_api_claim_sidecar_5781.py`, driving the real Typer apps on a git fixture:
  - after `start-implementation --actor claude`, the snapshot `agent == "claude"`, and the claim event's `policy_metadata` holds both the policy keys and `agent`;
  - a `--policy` carrying `"agent": "spoof"` still records `agent == "claude"`;
  - the same holds for `transition --to claimed` and for `agent status emit --to claimed --actor claude`;
  - after `transition --to planned`, the `agent`/`shell_pid` slots are empty and `implementer_of_record` is kept; a second actor then claims through `start-implementation`, and through host `agent action implement`, with no `--force`.
- `tests/status/test_claim_release.py`: the helper's delta shape, and that `move-task`'s planned additions come from it.

## Implementation

1. `claim_policy_metadata(shell_pid: int | None, agent: str, *, extra: Mapping[str, Any] | None = None)`. With `None`, omit the pid keys. `extra` merges first, so the claim keys win. Host call sites are unchanged.
2. API `_start_implementation`: pass `claim_policy_metadata(None, actor, extra=policy_dict)`. API `transition`: when `to_lane == CLAIMED`, do the same; when `to_lane == PLANNED`, pass `annotation_delta=planned_claim_release_delta()`. `agent status emit`: when the target resolves to `claimed`, pass `policy_metadata=claim_policy_metadata(None, actor)`.
3. `status/claim_release.py`: `planned_claim_release_delta() -> WPInnerStateDelta`, plus `planned_claim_release_fields() -> dict` for move-task's dict-shaped additions. Both are built from one definition. Re-export through `status/__init__.py`.
4. `done_bookkeeping`: the reviewer fallback reads the actor of the WP's latest `approved` transition from the event stream it already holds; `unknown` when there is none.

## Validation

`make test-fast`; `pytest tests/orchestrator_api tests/status tests/agent/test_orchestrator_commands_integration.py tests/consolidation -k "done_bookkeeping or claim"`; the move-task test files (`grep -rl tasks_move_task_hops tests`); `tests/specify_cli/cli/commands -k "status or move_task"` (out of matrix, run locally). ruff, `ruff format --check --force-exclude`, and mypy on the changed files.
