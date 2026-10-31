---
work_package_id: WP02
title: Bootstrap and recovery writers move onto the system actor
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-003
- SC-001
planning_base_branch: issue-6722-system-status-actor
merge_target_branch: issue-6722-system-status-actor
branch_strategy: Planning artifacts for this mission were generated on issue-6722-system-status-actor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6722-system-status-actor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-system-status-actor-01M67HTR
base_commit: 2b85289cdd6472c1e91c3f5d21e4ebdaa6561ffa
created_at: '2026-10-31T00:20:50.481411+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 2 - Writers
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent:
- tests/status/test_system_actor_bootstrap_6722.py
- tests/lanes/test_system_actor_6722.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/status/bootstrap.py
- src/specify_cli/lanes/recovery.py
- tests/status/test_system_actor_bootstrap_6722.py
- tests/lanes/test_system_actor_6722.py
- tests/lanes/test_implementation_recovery.py
- tests/specify_cli/lanes/test_recovery.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Bootstrap and recovery writers move onto the system actor

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

- The `finalize-tasks` bootstrap seed stores `{"tool": "finalize-tasks", "role": "system", "profile": None, "model": None}`.
- A recovery catch-up transition stores `{"tool": "recovery", "role": "system", "profile": None, "model": None}`.
- The reduced snapshot's `actor` slot still reads the bare tool for both (`finalize-tasks`, `recovery`).
- FR-002, FR-003.

## Context & Constraints

- Read: `contracts/system-actor.md` §2, `data-model.md` §SystemWriter rows 1–2.
- WP01 provides `specify_cli.status.actor.build_system_actor`; use it, do not assemble the dict.
- `RECOVERY_ACTOR` (`lanes/recovery.py:37`) must stay a `str`: line 80 passes it to
  `GuardContext(actor=RECOVERY_ACTOR, ...)`, whose `actor` is typed `str`. Wrap it at the emit
  site (`actor=build_system_actor(RECOVERY_ACTOR)`), do not convert the constant.
- Do not change the seed's `reason`, `policy_metadata`, `force` or ordering: this is an actor-only
  change.

## Branch Strategy

- **Strategy**: planning artifacts were generated on `issue-6722-system-status-actor`; completed
  changes merge back into it. Execution worktrees are allocated per computed lane from `lanes.json`.
- **Planning base branch**: `issue-6722-system-status-actor`
- **Merge target branch**: `issue-6722-system-status-actor`

## Subtasks & Detailed Guidance

### T001 – Red-first: the bootstrap seed's stored actor

- **Purpose**: prove the seed's shape through the real entry point.
- **Steps**: on a fixture mission with task files and no events, run the bootstrap seam
  (`specify_cli.status.bootstrap.bootstrap_status`) and read the log. Assert the exact 4-key dict
  for every seeded WP, and the reduced snapshot's `actor` slot is `finalize-tasks`. Observe the
  test fail on the base (it stores the string).
- **Files**: `tests/status/test_system_actor_bootstrap_6722.py`.
- **Notes**: assert the seed still has `from_lane == genesis`, `to_lane == planned`,
  `force is False` and its `reason`, so the test cannot pass by loosening something else.

### T002 – Red-first: the recovery catch-up's stored actor

- **Purpose**: prove the sweep's shape, including that the sweep actually emitted.
- **Steps**: drive the recovery path that reconciles a crashed lane (`_reconcile_wp` /
  `reconcile_status` in `lanes/recovery.py`) on a fixture whose WP is stuck in `claimed` with a
  branch that has commits. Assert at least one transition was emitted and each one's actor is the
  4-key dict with `tool == "recovery"`. Assert the snapshot `actor` slot is still `recovery`.
- **Files**: `tests/lanes/test_system_actor_6722.py`.

### T003 – Move `status/bootstrap.py` onto the builder

- **Files**: `src/specify_cli/status/bootstrap.py:194`.
- **Notes**: one line; keep the surrounding `TransitionRequest` untouched.

### T004 – Move `lanes/recovery.py` onto the builder and update the existing assertions

- **Files**: `src/specify_cli/lanes/recovery.py:817`; `tests/lanes/test_implementation_recovery.py`
  (lines ~540, ~621, ~661 compare `event.actor == RECOVERY_ACTOR`).
- **Steps**: wrap the constant at the emit site; update the existing comparisons to compare the
  identity (`actor_identity_str(event.actor) == RECOVERY_ACTOR`) or the dict, whichever reads more
  honestly at each site. Keep `GuardContext(actor=RECOVERY_ACTOR)` untouched.
- **Notes**: `tests/specify_cli/lanes/test_recovery.py` compares the constant in a `GuardContext`
  construction, which stays correct; verify it still passes rather than editing it blindly.

## Test Strategy

```bash
uv run --frozen pytest tests/status/test_system_actor_bootstrap_6722.py tests/lanes/test_system_actor_6722.py -q
uv run --frozen pytest tests/lanes tests/specify_cli/lanes tests/status -q
uv run --frozen ruff check src/specify_cli/status/bootstrap.py src/specify_cli/lanes tests/lanes tests/status/test_system_actor_bootstrap_6722.py
uv run --frozen mypy src/specify_cli/status/bootstrap.py src/specify_cli/lanes/recovery.py
```

## Risks & Mitigations

- **A vacuous recovery test.** The sweep swallows every exception; assert the emission count and
  the lane first, so "no events" cannot pass as "no wrong events".
- **Converting `RECOVERY_ACTOR` to a dict** breaks `GuardContext` typing and the existing guard
  tests. Wrap at the emit site only.

## Review Guidance

- Is the seed's non-actor payload byte-identical to the base? Diff the `to_dict()` keys other than
  `actor` in the test.
- Did the constant stay a `str`?

## Progress & Status

- `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP02 --to <status>`
