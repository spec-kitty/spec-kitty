---
work_package_id: WP03
title: next commits its coordination event row (#5938)
dependencies: []
requirement_refs:
- FR-004
- C-001
- C-003
planning_base_branch: fix/7545-cli-owns-its-commits
merge_target_branch: fix/7545-cli-owns-its-commits
branch_strategy: Planning artifacts for this mission were generated on fix/7545-cli-owns-its-commits. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7545-cli-owns-its-commits unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Commits
history:
- at: '2026-11-11T16:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/next_cmd.py
create_intent:
- tests/specify_cli/cli/commands/test_next_commits_coordination_row_5938.py
- docs/changelog/unreleased/5938-next-commits-coordination-row.fixed.md
execution_mode: code_change
owned_files:
- src/runtime/next/next_invocation_lifecycle.py
- src/specify_cli/cli/commands/next_cmd.py
- tests/specify_cli/cli/commands/test_next_commits_coordination_row_5938.py
- docs/changelog/unreleased/5938-next-commits-coordination-row.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – `next` commits its coordination event row (#5938)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `implementer-ivan` (role `implementer`).

---

## Objectives & Success Criteria

- After `spec-kitty next --result success` on a coordination Mission, the coordination
  worktree is clean, and the MissionNextInvoked row is on the coordination branch.
- The operator's own uncommitted edits in that worktree stay uncommitted (C-001).
- A refused or failed commit prints a warning and never fails `next`.
- Closes #5938. The root-checkout `kitty-ops/lifecycle/` record is PR #7557's concern; do not
  touch it.

## Context & Constraints

- Root cause: `next_cmd.py` `_emit_mission_next_invoked` →
  `runtime/next/next_invocation_lifecycle.py:337` `emit_mission_next_invoked` appends via
  `mission_v1/events.emit_event` and never commits.
- The #5669 ruling: `mission-events.jsonl` stays real dirt, so commit it; never exempt it.
- Canonical shape: `coordination/status_transition.py::_commit_status_artifacts_to_coord`:
  `resolve_placement_only(repo_root, slug, kind=STATUS_STATE)` gives the target, then
  `safe_commit(repo_root=..., worktree_root=<coord worktree>, target=..., paths=(file,),
  capability=STANDARD)`.
- Layering: `runtime` must not gain a module-level `specify_cli` import. Do the commit in
  `next_cmd.py`; the runtime function only returns the path it wrote.
- Owned mode already commits everything via `_commit_owned_next_mutations`; leave that path alone.

## Branch Strategy

- **Strategy**: single_branch, direct in the repository root checkout
- **Planning base branch**: fix/7545-cli-owns-its-commits
- **Merge target branch**: fix/7545-cli-owns-its-commits

## Subtasks & Detailed Guidance

### Subtask T009 – Red test

- New file `tests/specify_cli/cli/commands/test_next_commits_coordination_row_5938.py`. Build a
  real repository (`git init`, `spec-kitty init` via the CLI app or a minimal `.kittify`), then
  a coordination Mission (`agent mission create --topology coord`) with one WP. Run
  `finalize-tasks` and `record-analysis`, then invoke `next --agent claude --mission <m>
  --json --result success` in-process (CliRunner), or as a subprocess if the in-process run
  is impractical. Assert that `git status --porcelain` in the coordination worktree is empty
  and that `git log -1 --format=%s` there names the next invocation.
- A second case plants an operator file in the coordination worktree before `next` and asserts
  it is still untracked afterwards.
- Mark the module `integration` if it needs more than a few seconds. Commit red first.

### Subtask T010 – Return the written path

- `emit_mission_next_invoked(...) -> Path | None`: return `feature_dir / MISSION_EVENTS_FILE`
  when a row was persisted, else `None`. `emit_event` never raises, so check that the file
  exists. Update the docstring. Callers that ignore the return value are unaffected.

### Subtask T011 – Commit it

- In `next_cmd.py`, wherever `_emit_mission_next_invoked` is called on the non-owned path, take
  the returned path. When it lies inside a coordination worktree (resolve through the
  placement seam: `placement_seam(repo_root, slug).write_dir(STATUS_STATE)` returns a
  `WriteLocation` whose `surface` is COORD and whose `surface_root` is the worktree. Prefer
  having `emit_mission_next_invoked` return that `WriteLocation`'s root alongside the path so
  you do not re-resolve), call a new helper `_commit_next_event_row(repo_root, slug, path,
  worktree_root)`. It uses `resolve_placement_only(..., kind=STATUS_STATE)` + `safe_commit`,
  with message `chore(next): record next invocation for <slug>`. Catch `RuntimeError` /
  `subprocess.CalledProcessError` / `OSError` and print a one-line warning (stderr in JSON mode).
- Do not stage anything else.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/cli/commands/test_next_commits_coordination_row_5938.py tests/specify_cli/next tests/next tests/specify_cli/cli/commands/test_next_owned_fact.py -q
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_commit_scope_owner.py tests/architectural/test_safe_commit_import_boundary.py tests/architectural/test_no_write_side_rederivation.py -q
```

## Risks & Mitigations

- A commit census gate (`test_commit_scope_owner.py`) may require registering the new
  `safe_commit` call site. Register it honestly if it does; it is not an allowlist ratchet.

## Review Guidance

- Only the one file is staged; no runtime-to-specify_cli module-level import; red first.
