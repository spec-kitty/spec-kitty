---
work_package_id: WP02
title: Door parity and the neighbouring ratchets
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-007
- FR-008
- FR-009
- SC-003
- SC-004
- SC-005
- C-003
planning_base_branch: issue-6514-reject-invalid-forced-status-rewind
merge_target_branch: issue-6514-reject-invalid-forced-status-rewind
branch_strategy: Planning artifacts for this mission were generated on issue-6514-reject-invalid-forced-status-rewind. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6514-reject-invalid-forced-status-rewind unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-reject-invalid-forced-status-rewind-01M68J8B
base_commit: 3e9867e3f90b0b54e4dcefce699a84950d44284b
created_at: '2026-10-31T10:08:01.199996+00:00'
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Parity
history:
- at: '2026-10-31T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/status/test_forced_rewind_door_parity.py
create_intent:
- tests/status/test_forced_rewind_door_parity.py
execution_mode: code_change
model: ''
owned_files:
- tests/status/test_forced_rewind_door_parity.py
- tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6514'
---
# Work Package Prompt: WP02 – Door parity and the neighbouring ratchets

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter and
behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

WP01 closes the hole for every door at once, because the rule lives in the FSM. This WP
**proves** that rather than assuming it, and proves nothing else moved.

Done when:

1. the pointerless forced `for_review → in_progress` through `orchestrator-api wp
   transition` is refused with no append, and the same request with `--review-ref`
   succeeds — both on one fixture;
2. `move-task`'s forced rewind on the same edge still exits 0 and still records
   `to_lane=in_progress` with the `force-override` pair it supplies;
3. the other forced edges are unchanged: `done → in_progress`, `canceled → planned`,
   `planned → in_progress`, `for_review → planned`, `in_review → in_progress`.

## Context & Constraints

- Spec FR-004, FR-007, FR-008, FR-009, SC-003/004/005, C-003. Contract
  `contracts/forced-rewind-refusal.md` C-2, C-3. Research §3.
- **Do not patch a door.** If the orchestrator door needs a code change to refuse, that is
  a WP01 defect — fix the shared rule and say so in the history note. The whole point of
  FR-005/C-001 is that no per-surface rule exists.
- **Do not edit `src/specify_cli/cli/commands/agent/tasks_transition_core.py`.** It already
  conforms (`emit_review_ref = "force-override"` on this edge). It is a ratchet, not a fix.
- `tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py::
  test_unforced_non_done_backward_move_is_unchanged` already pins the `move-task` shape;
  extend it only if a gap exists, never weaken it.

## Branch Strategy

- **Planning base branch**: `main`
- **Merge target branch**: `main`

Implement with `spec-kitty agent action implement WP02 --agent pi --mission reject-invalid-forced-status-rewind-01M68J8B`.

## Subtasks & Detailed Guidance

### T006 – Red-first door-parity test (own commit)

New `tests/status/test_forced_rewind_door_parity.py`. Reuse the real-route harness in
`tests/specify_cli/orchestrator_api/test_transition_subtask_gate.py`: a real git repo
(`git init -b main`, a commit), a flat `kitty-specs/<slug>/` with `meta.json`, and a
`status.events.jsonl` seeded so WP01 sits in `for_review`
(`planned → claimed → in_progress → for_review`; the `for_review` hop needs its subtask
roster satisfied or an explicit force — read that harness's own seeding comments before
choosing). Drive `specify_cli.orchestrator_api.commands.app` with
`["transition", "WP01", "--to", "in_progress", "--actor", "test-orch", "--force", ...]`,
matching the argument names that harness already uses. Neutralize `_status_fan_out` the
same way it does.

Assertions, same fixture:

- without `--review-ref`: non-zero exit, `status.events.jsonl` SHA-256 unchanged, and the
  error text carries `review_ref` + `--review-ref`;
- with `--review-ref`: exit 0, one row appended, `to_lane == "in_progress"`.

Commit: `test(6514): pin door parity for the forced rewind refusal (red)`.

### T007 – `move-task` ratchet (own commit)

Add one regression test (in this file, or extend the existing one if it already asserts
everything) that drives `agent tasks move-task WP01 --to in_progress` on a `for_review` WP
and asserts exit 0, the appended row's `(from_lane, to_lane) == ("for_review",
"in_progress")`, `force is True`, and `review_ref == "force-override"`. The last assertion
is the point: it shows *why* the conforming surface keeps working.

Commit: `test(6514): pin that move-task's forced rewind still carries its sentinel`.

### T008 – The other forced edges are unchanged (own commit)

A parametrized unit test over `wp_state_for(from).check_transition(to, GuardContext(force=True,
actor="codex", reason="why"))` for the edges in contract C-3 that are outside
`REVIEW_REF_REQUIRED_EDGES`, asserting `(True, None)` with `review_ref=None`. Keep it a
plain table so a future change to the edge set shows up as a diff here.

Commit: `test(6514): pin that force elsewhere is unchanged`.

## Test commands

```bash
uv run pytest -q tests/status/test_forced_rewind_door_parity.py
uv run pytest -q tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py
uv run pytest -q tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py -k for_review
uv run pytest -q tests/specify_cli/orchestrator_api/test_transition_subtask_gate.py
```

## Definition of Done

- Zero changes under `src/` for this WP, unless the door-parity test exposes a real gap —
  in which case the fix lands in the shared rule and the history note says so.
- Every assertion has a same-fixture contrast (refused vs appended).
