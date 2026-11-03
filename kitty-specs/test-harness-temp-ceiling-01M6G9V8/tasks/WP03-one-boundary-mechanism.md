---
work_package_id: WP03
title: One boundary mechanism
dependencies: []
requirement_refs:
- FR-005
- FR-006
- C-002
- C-003
- SC-004
planning_base_branch: issue-7076-test-harness-temp-ceiling
merge_target_branch: issue-7076-test-harness-temp-ceiling
branch_strategy: Planning artifacts for this mission were generated on issue-7076-test-harness-temp-ceiling. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7076-test-harness-temp-ceiling unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Story work
history:
- at: '2026-11-03T00:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/unit/test_root_walk_has_one_boundary.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/paths.py
- src/specify_cli/task_utils/support.py
- tests/unit/test_root_walk_has_one_boundary.py
- tests/specify_cli/charter_preflight/test_cli.py
- tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py
- tests/status/test_lock_fallback_never_mints_marker.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – One boundary mechanism

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

- `locate_project_root(start: Path | None = None)` and
  `find_repo_root(start: Path | None = None)` take no `stop` parameter, and passing one raises
  `TypeError` — the parameter is gone, not accepted-and-ignored.
- Their docstrings describe git's ceiling as the boundary and no longer explain a `stop=` a
  caller cannot pass.
- The three test modules that passed `stop=` bound the walk with their own
  `GIT_CEILING_DIRECTORIES` and keep the verdicts they had: they still prove "no project root
  here" and "the boundary is examined but nothing above it is".
- `session_start._find_project_root` keeps its `stop=` (C-002). Its walk does not read the
  ceiling; deleting its only bound would make its four callers non-hermetic. Record that in the
  module docstring or a comment so the next reader knows it is deliberate, and name it in the PR.

## Context & Constraints

- `src/specify_cli/task_utils/support.py::find_repo_root` forwards `stop` to
  `locate_project_root` and keeps its own `boundary` loop guard for its plain-`.git` fallback.
  Both go.
- The ceiling contract (ceiling directory **examined**, walk stops after it) is already pinned by
  `tests/tasks/test_tasks_support.py::test_find_repo_root_plain_git_fallback_stops_at_a_git_ceiling`
  and `tests/specify_cli/core/test_paths.py`. Those must stay green: they are the proof that
  removing `stop=` does not remove the boundary.
- PR #7082 (issue #7056, still open) rewrites these two functions *around* `stop=` and keeps it
  under its own `C-005`. Expect a conflict there; resolve it by keeping this WP's removal.

## Branch Strategy

- **Strategy**: the mission's lane worktree, branched from the mission branch.
- **Planning base branch**: `issue-7076-test-harness-temp-ceiling`
- **Merge target branch**: `issue-7076-test-harness-temp-ceiling` (the operator merges; no push
  to `main`)

## Subtasks & Detailed Guidance

### T008 — Red first

Create `tests/unit/test_root_walk_has_one_boundary.py` (`unit`, `fast`):

1. `inspect.signature(locate_project_root)` has no `stop` parameter; same for `find_repo_root`.
2. Passing `stop=` raises `TypeError` for both (call them with a path and the keyword; catch
   `TypeError`). **Do not** rely on `pytest.raises(match=...)` over the message — assert the
   parameter's absence, which is the contract.
3. One behavioural control: with `monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(jail))`, a
   directory below `jail` that has no `.git`/`.kittify` resolves to `None` while a `jail` that
   *is* a project resolves to `jail` — i.e. the boundary is examined (same-fixture positive
   control).

Red on `main`: (1) and (2) fail because the parameter exists.

### T009 — Remove the parameter

`src/specify_cli/core/paths.py`:

- Signature → `def locate_project_root(start: Path | None = None) -> Path | None`.
- Delete `boundary = stop.resolve() if stop is not None else None` and the
  `if boundary is not None and candidate == boundary: break`.
- Rewrite the docstring's `stop:` paragraph into the ceiling paragraph it already has (keep the
  ceiling explanation and the reason tests used to need a local bound — one sentence, past tense).

`src/specify_cli/task_utils/support.py`:

- Signature → `def find_repo_root(start: Path | None = None) -> Path`.
- Call `locate_project_root(current)` without forwarding.
- Delete `boundary` and its break from the fallback loop; keep the `candidate in ceilings` break.

Run `uv run mypy src/specify_cli/core/paths.py src/specify_cli/task_utils/support.py` and
`uv run ruff check src/specify_cli/core/paths.py src/specify_cli/task_utils/support.py`.

### T010 — The three callers

| File | Line | Change |
| --- | --- | --- |
| `tests/specify_cli/charter_preflight/test_cli.py:106` | `partial(find_repo_root, stop=tmp_path)` | drop the `monkeypatch.setattr` and set `GIT_CEILING_DIRECTORIES` to `tmp_path` instead |
| `tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py:119` | `lambda start=None: locate_project_root(start, stop=tmp_path)` | drop the `monkeypatch.setattr`; set the ceiling to `tmp_path` |
| `tests/status/test_lock_fallback_never_mints_marker.py:61` | `locate_project_root(child, stop=tmp_path)` | set the ceiling to `tmp_path`, call `locate_project_root(child)` |

Each keeps its existing `monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)` where present,
and each keeps (or gains) the comment explaining that the walk is bounded to this test's own
tree. The rewritten comments must say the bound is `GIT_CEILING_DIRECTORIES` now, not a `stop`
parameter.

## Review Guidance

- Is the removal complete — no stale `stop` in docstrings, `partial(...)`, or type stubs?
- Do the three modules still fail if the bound is removed (i.e. is the ceiling actually what holds
  them)?
- Did `session_start._find_project_root` stay untouched?

## Definition of Done

- T008's test was red before T009/T010 and is green after.
- `uv run pytest tests/unit/test_root_walk_has_one_boundary.py tests/specify_cli/charter_preflight/test_cli.py tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py tests/status/test_lock_fallback_never_mints_marker.py tests/tasks/test_tasks_support.py tests/specify_cli/core/test_paths.py -q` green.
- Ruff and mypy clean on the two `src/` files.
