---
work_package_id: WP02
title: Accept --base on the dispatched agent implementation path
dependencies: []
requirement_refs:
- FR-004
- FR-005
- SC-003
- SC-004
planning_base_branch: issue-6753-stale-coord-lane-base
merge_target_branch: issue-6753-stale-coord-lane-base
branch_strategy: Planning artifacts for this mission were generated on issue-6753-stale-coord-lane-base. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6753-stale-coord-lane-base unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Make the remedy reachable
history:
- timestamp: '2026-10-30T23:40:00Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_cores.py
- tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py
role: implementer
tags: []
tracker_refs:
- '#6753'
wp_code: WP02
---

# Work Package Prompt: WP02 – Accept `--base` on the dispatched agent path

## ⚡ Do This First: Load Agent Profile

Load your assigned agent profile with the `spk-charter-profile-load` skill, profile id
**`python-pedro`**, and adopt it for the whole work package. Then read
`kitty-specs/stale-coord-lane-base-01M67HRA/spec.md` and `plan.md`.

## Objective

`spec-kitty next` and the `/spec-kitty.implement` shim both dispatch
`spec-kitty agent action implement <WP> --agent <name>`. That command has no `--base`,
so an agent following the documented loop cannot act on the remedy #6753 names; only
the internal top-level `spec-kitty implement <WP> --base <ref>`
(`src/specify_cli/cli/commands/implement.py`, `base` option at ~line 330) can. Add the
same option to `agent action implement`, thread it through `ImplementRequest` into the
`top_level_implement(...)` create-path dispatch, and prove it reaches the allocator
seam — with every existing base-refusal route still firing unchanged.

**Do not** invent new base semantics: `resolve_lane_base_or_refuse` already owns them
(`UnhonorableBaseError` for reuse, crash recovery, dependency lanes, and a base
detached from the recorded planning commit; the planning-lane "ignored" warning for a
repository-root lane). This WP only carries the operator's value to that seam.

## Context & Constraints

- **Entry point**: `src/specify_cli/cli/commands/agent/workflow.py`, the
  `@app.command(name="implement")` function (~line 1546). It builds an
  `ImplementRequest` (~line 1634) and defines a `_create_workspace()` closure
  (~line 1710) that calls `top_level_implement(wp_id=..., mission=..., json_output=False,
  recover=False, acknowledge_not_bulk_edit=..., actor=agent)`. That closure runs only
  when the workspace must be created (`_ensure_workspace_materialized`) — the reuse
  path deliberately goes through `reenter_lane_self_heal` instead. Threading `base`
  into the closure is therefore enough to reach the allocator on exactly the fresh
  route, and the allocator's own `UnhonorableBaseError` guard owns what happens on a
  reuse/crash-recovery route.
- **Data carrier**: `ImplementRequest` lives in
  `src/specify_cli/cli/commands/agent/workflow_cores.py` and is documented as "the raw
  `agent action implement` CLI options, unresolved". Add `base: str | None = None`
  (defaulted, so existing constructors keep working) and set it from the Typer option.
- **Help text**: mirror the top-level `--base` help wording (see `implement.py`) so the
  two surfaces describe one behaviour. Keep the option typed
  `Annotated[str | None, typer.Option("--base", help=...)] = None`.
- **Shims need no change**: `specify_cli/shims/generator.py` emits
  `spec-kitty agent action implement {args} --agent {agent}`, so `{args}` already
  forwards a user-supplied `--base`.
- Do not touch `implement.py`, the allocator, or any other command surface. Keep the
  diff to the option surface plus the one value threaded into the existing closure.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first: the option does not exist

Create `tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py`.
Drive the real command through `typer.testing.CliRunner`:
`CliRunner().invoke(workflow.app, ["implement", "WP01", "--mission", "<slug>", "--agent",
"<agent>", "--base", "main"])`. Against the current tree this exits 2 with
`No such option: --base` — assert that red state first, then flip the assertion to the
post-fix expectation. Reuse an existing fixture in the same directory rather than
building a new harness (see `test_implement_runtime_frontmatter_claim.py` for the
non-git tmp-repo + monkeypatched `safe_commit`/branch pattern, and
`tests/lane_test_utils.py` for the lane manifest helper). Monkeypatch the create-path
dispatch (`top_level_implement` as imported by `workflow`) to capture kwargs so the
test observes the value that reaches the allocator seam without creating a worktree.

### Subtask T008 – Carry the value

Add `base` to `ImplementRequest` (defaulted) and pass it from the Typer option into the
request. Then pass `base=request.base` (or the resolved local) into the
`top_level_implement(...)` call inside `_create_workspace()`. No other behaviour change:
do not resolve, validate or normalise the ref here — `implement.py`'s
`_resolve_effective_base` owns validation, including the planning-lane "ignored"
warning.

### Subtask T009 – The option surface

Add the Typer option parameter to the `implement` command with help text matching the
top-level command's. Keep parameter ordering/`Annotated` style consistent with the
neighbouring options so `--help` stays readable.

### Subtask T010 – Positive control and the refusal ratchet

In the same test module:

- same invocation **without** `--base` → the captured base is `None` (the positive
  control that proves the capture can observe the value, per
  `acceptance-criteria-non-vacuity`);
- an already-allocated lane plus `--base` still raises the reuse-route
  `UnhonorableBaseError` (`UnhonorableBaseError(route="reuse", ...)`) — either through
  the allocator seam directly or through the CLI, whichever the fixture supports
  cheaply. This is FR-005: the new option must not buy a silent no-op.

### Subtask T011 – Validate

Run, and record the results:

```
uv run pytest tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py -q
uv run pytest tests/specify_cli/cli/commands/agent -q
uv run pytest tests/agent -q
uv run ruff check src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/cli/commands/agent/workflow_cores.py tests/specify_cli/cli/commands/agent/test_issue_6753_agent_action_implement_base.py
uv run ruff format --check src/specify_cli/cli/commands/agent/workflow.py src/specify_cli/cli/commands/agent/workflow_cores.py
```

Also confirm the help surface changed as intended:
`uv run spec-kitty agent action implement --help | grep -A2 -- --base`.

Do **not** run `make test-full` or any whole-repo heavy sweep.

## Definition of Done

- T007's test was red (`No such option: --base`) before the change and is green after;
  paste both outputs in the review hand-off.
- `agent action implement --base <ref>` reaches the create-path dispatch with the value
  unchanged; without `--base` it is `None`; the reuse refusal still fires.
- Nothing but the two `agent/` modules changed; allocator and top-level `implement`
  untouched.
- `uv run pytest tests/specify_cli/cli/commands/agent tests/agent -q` green; ruff clean.
