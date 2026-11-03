---
work_package_id: WP02
title: Every emitter prints the scoped recipe
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7108-subtask-recipe-wp-scoping
merge_target_branch: issue-7108-subtask-recipe-wp-scoping
branch_strategy: Planning artifacts for this mission were generated on issue-7108-subtask-recipe-wp-scoping. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7108-subtask-recipe-wp-scoping unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 2 - Every emitter prints the scoped recipe
history:
- at: '2026-10-30T09:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- src/runtime/next/prompt_builder.py
- tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py
- tests/next/test_prompt_builder_review_base.py
- tests/integration/test_prompt_builder_owned_arms.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Every emitter prints the scoped recipe

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according
to its guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting; if
this WP was returned from review, resolve every feedback item first and record each with
`spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

Every surface that tells an operator or agent how to mark subtasks done prints a
command that actually works on the normal case — a mission whose WPs share
`T001..T00n`. Four sites, one renderer from WP01.

The reproduction you must be able to show, before and after:

```
$ spec-kitty agent tasks move-task WP02 --to for_review --mission port-completion-01M6FZ0K
Cannot move WP02 to for_review - unchecked subtasks:
  - [ ] T001
  - [ ] T002

Mark these complete first:
  spec-kitty agent tasks mark-status T001 --status done        <-- BEFORE (dies)
  ...
```

**Before**: that advice is refused by `mark-status` on a shared-id mission
(`T001 is a subtask of WP01, WP02 …; pass --wp to select one.`), so the operator
reaches for `--force`.

**After**: the advice reads
`spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission port-completion-01M6FZ0K`
and running it clears the gate on retry.

## Context

- `src/specify_cli/cli/commands/agent/tasks_transition_core.py::_guard_subtasks` —
  the pure decision core that renders the refusal. It is deliberately I/O-free;
  the renderer is pure text, so importing it adds no I/O (`MoveTaskRequest` already
  carries `task_id` = the WP, and `mission_slug`).
- `src/runtime/next/prompt_builder.py::_completion_lines` — the implement "WHEN
  DONE" block. `wp_id` is a parameter; `owned` supplies the owned root.
- `src/specify_cli/cli/commands/agent/workflow_executor.py` — three sites
  (around lines 1608, 1686 and 1743) that repeat the same f-string; all three have
  `normalized_wp_id` in scope.
- `src/specify_cli/cli/commands/agent/tasks_shared.py::_check_unchecked_subtasks` —
  where the unchecked ids come from; **do not change it**.

## Subtasks

### T001 — Red-first refusal test

Create `tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py`.
Build a `MoveTaskRequest` for `task_id="WP02"`, `mission_slug="port-completion-01M6FZ0K"`,
`unchecked_subtasks=("T001", "T002")`, `target_lane="for_review"`, `force=False`,
and assert `_guard_subtasks(req).error` contains
`spec-kitty agent tasks mark-status T001 --wp WP02 --status done --mission port-completion-01M6FZ0K`.
It must fail on unmodified `src`. Also assert:

- the refusal still fires (not `None`), and still lists both ids under
  `unchecked subtasks` — the guard's verdict is unchanged (C-003);
- `mission_slug=None` renders a valid command with no `--mission` token and no
  literal `None`.

### T002 — Wire the refusal

Replace the inline f-string in `_guard_subtasks` with
`mark_status_recipe([task], wp_id=req.task_id, mission_slug=req.mission_slug)`.
Keep the surrounding text (`Mark these complete first:`, the `--force` hint) byte
identical so only the command lines change.

### T003 — Behavioural proof (SC-001)

In the same test file, add a test that takes the emitted command **string**, parses
it back into the `mark_status` invocation (e.g. `shlex.split` minus the leading
`spec-kitty agent tasks`), and drives the real entry point against a two-WP,
shared-id fixture — a mission directory whose `tasks/WP01-*.md` and
`tasks/WP02-*.md` both author `subtasks: [T001, T002]`, with a seeded status
surface. Assert exit code 0 and that the snapshot for **WP02** records `T001` as
`done` while WP01's does not. Reuse the existing fixture helpers rather than
inventing a parallel one (`tests/specify_cli/core/test_subtask_rows_snapshot.py`
and `tests/_support/status_seed.py` show the shape). If driving the full CLI in a
unit test proves too heavy, drive `_do_mark_status` — but do not stub the owner
resolution, because owner resolution is the behaviour under proof.

### T004 — Wire the prompt builder

`_completion_lines`: when `subtask_ids` is non-empty, render the recipe via
`mark_status_recipe(subtask_ids, wp_id=wp_id, mission_slug=mission_slug, owned_root=... when owned)`.
Keep the `else` branch's exact wording —
`No subtask completion command is needed; this work package declares no subtasks.`
(FR-006) — and keep the `move-task` line unchanged.

### T005 — Wire the three runbook sites

All three `workflow_executor` sites now render the same scoped command. Grep the
file for `mark-status` and confirm exactly three emitters remain, all routed
through the renderer.

### T006 — Update the pinned assertions

`tests/next/test_prompt_builder_review_base.py` and
`tests/integration/test_prompt_builder_owned_arms.py` currently pin the unscoped
string. Update them to the scoped one; the owned arm must assert `--wp WP02` and
`--owned-checkout <root>` both present, in that order relative to `--status`/`--mission`.

### T007 — All-sites proof (SC-002, SC-003)

In the new test file, assert the three `workflow_executor` recipes and the prompt
recipe each contain `--wp` (SC-002), and that a WP with an empty authored roster
renders zero `mark-status` lines (SC-003).

## Definition of Done

- [ ] `uv run pytest tests/specify_cli/cli/commands/agent/test_move_task_unchecked_recipe_scoped.py tests/next/test_prompt_builder_review_base.py tests/integration/test_prompt_builder_owned_arms.py -q` — green.
- [ ] `uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py -q` — still green (the byte-frozen `--help` fixtures are untouched).
- [ ] `uv run pytest tests/specify_cli/cli/commands/agent/test_mark_status_owner_authority.py tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py -q` — still green (owner refusals unchanged).
- [ ] `uv run pytest tests/specify_cli/core/ -q` — green.
- [ ] `git diff --stat` touches only the six owned files.
- [ ] No test skipped, xfailed or weakened; no refusal removed.

## Risks & Mitigations

- **Adding I/O to a pure core.** `tasks_transition_core` must not gain a file read.
  The renderer is text-only; if your diff adds a resolver call there, that is a
  review finding.
- **Missing a fourth emitter.** `grep -rn "mark-status" src/` after wiring: the
  only remaining literals should be the `--help` docstrings in
  `tasks.py`/`tasks_mark_status.py` (frozen) and the renderer itself.
- **Prompt byte-stability tests elsewhere.** Grep `tests/` for
  `mark-status T001 --status done` and update every pin, not just the two named here.
