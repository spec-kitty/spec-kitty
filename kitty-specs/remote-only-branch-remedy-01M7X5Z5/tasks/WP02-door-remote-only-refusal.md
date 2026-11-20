---
work_package_id: WP02
title: Typed remote-only refusal at the status read door
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-001
- C-001
- C-002
- C-003
- SC-002
planning_base_branch: issue-5287-remote-only-coord-remedy
merge_target_branch: issue-5287-remote-only-coord-remedy
branch_strategy: Planning artifacts for this mission were generated on issue-5287-remote-only-coord-remedy. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5287-remote-only-coord-remedy unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Status read door
history:
- at: '2026-11-20T19:14:47Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent:
- tests/status/test_read_surface_remote_only_5287.py
- tests/specify_cli/cli/commands/agent/test_tasks_status_remote_only_5287.py
- docs/changelog/unreleased/5287.fixed.md
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/coordination/status_service.py
- src/specify_cli/status/read_surface.py
- tests/status/test_read_surface_remote_only_5287.py
- tests/specify_cli/cli/commands/agent/test_tasks_status_remote_only_5287.py
- tests/runtime/next/test_board_query_read_door_7507.py
- docs/adr/4.x/2026-11-06-2-one-status-read-contract.md
- docs/changelog/unreleased/5287.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Typed remote-only refusal at the status read door

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress** with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

A status read whose declared ref source is a branch with no local head refuses with `StatusSurfaceRefRemoteOnly` (code `STATUS_SURFACE_REF_REMOTE_ONLY`), a subtype of `StatusSurfaceRefUnreadable`, whose message carries the WP01 remedy. Applies to `COORD_BRANCH_REF` and `MISSION_BRANCH_REF`. FR-006..FR-009, NFR-001, NFR-002, SC-002.

## Context & Constraints

- Operator ruling 1 (binding): the door does NOT read the remote-tracking ref. No new read source, no fallback (ADR 2026-11-06-2: one declared source per cell, typed error).
- NFR-001: zero added subprocesses on a successful read. Classify only after `read_status_ref` raises.
- Classification rule: after `StatusSurfaceRefUnreadable` from a `refs/heads/<b>` ref, if `ref_names_object(repo_root, "refs/heads/<b>")` is False → remote-only. If it is True (the ref exists but names a missing object = corruption) → re-raise the original unreadable error unchanged.
- A coordination branch the probe classifies as DELETED keeps raising `CoordinationBranchDeleted` (unchanged, decided earlier).
- `for_write=True` paths are untouched (#5936 is separate).
- `ref_source_remedy` stays unchanged.
- Out of scope: #7449 / `MigrationResult`.

## Branch Strategy

- **Strategy**: single_branch (settled at finalize)
- **Planning base branch**: issue-5287-remote-only-coord-remedy
- **Merge target branch**: issue-5287-remote-only-coord-remedy
- Run `spec-kitty agent action implement WP02 --agent claude --mission remote-only-branch-remedy-01M7X5Z5`.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first CLI ATDD (R1)

Create `tests/specify_cli/cli/commands/agent/test_tasks_status_remote_only_5287.py`. Fixture: `make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="absent", remote_only=True)`. Drive the pre-existing entry point — the typer app for `agent tasks status` via `CliRunner` (look at `tests/specify_cli/cli/commands/agent/test_tasks_status_cmd_seam.py` / `test_agent_status_surface_refusals.py` for how they invoke it and chdir/`--mission`) with `--json`. Assert exit code != 0, the JSON error message contains `STATUS_SURFACE_REF_REMOTE_ONLY`, `branch <b> coord-remote/<b>`, and the doctor `--fix` command. Positive control on the same fixture: run `git -C <root> branch <b> coord-remote/<b>` and re-invoke → exit 0. Commit alone first; it must be red on the base.

### Subtask T008 – Subtype

In `status_service.py` add `STATUS_SURFACE_REF_REMOTE_ONLY = "STATUS_SURFACE_REF_REMOTE_ONLY"` and

```python
class StatusSurfaceRefRemoteOnly(StatusSurfaceRefUnreadable):
    error_code: str = STATUS_SURFACE_REF_REMOTE_ONLY
    def __init__(self, *, repo_root: Path, ref: str, path: str, branch: str, remedy: str) -> None: ...
```

Call `RuntimeError.__init__` with: `Cannot read {path}: the branch {branch!r} exists only on a remote; this checkout has no local branch for it. A status history is never read from a remote-tracking ref. {remedy} Error code: STATUS_SURFACE_REF_REMOTE_ONLY.` Keep `repo_root/ref/path/detail` attributes populated (detail = "no local branch"). Export via `__all__` if the module declares one; re-export from `specify_cli.status` only if `StatusSurfaceRefUnreadable` is re-exported there.

### Subtask T009 – COORD_BRANCH_REF

In `read_surface.py::_coord_ref_decision`, wrap the `read_status_ref` prefetch: on `StatusSurfaceRefUnreadable as exc`, call a module helper `_remote_only_refusal(repo_root, ref, path, follow_up) -> StatusSurfaceRefRemoteOnly | None` (returns None unless `not ref_names_object(...)`); raise it `from exc` when not None, else re-raise. `follow_up` = `coordination_doctor_command(mission_dir_name)` (from `mission_runtime.coord_remedy`). The remedy = `remote_only_steps(remote_only_branch(repo_root, branch), repo_root, follow_up)`.

### Subtask T010 – MISSION_BRANCH_REF + door unit tests

In `_ref_text(surface)` (read the function first), apply the same helper when `surface.source is StatusReadSource.MISSION_BRANCH_REF` and `read_status_ref` raises; `follow_up` = `"re-run the command"` (phrase it as an imperative clause that reads well after "then"). Door tests in `tests/status/test_read_surface_remote_only_5287.py`:
- COORD remote-only → `StatusSurfaceRefRemoteOnly`, `isinstance(..., StatusSurfaceRefUnreadable)`, code, remedy present.
- MISSION_BRANCH_REF remote-only: a `topology_source: default` Mission whose topic branch is pushed to a bare remote and deleted locally (study `tests/status/test_read_surface_door.py` / `test_status_read_matrix.py` for how they build the MISSION_BRANCH_REF cell; reuse their builders).
- Negative control: a local `refs/heads/<b>` pointing at a missing object (write the ref file directly with a bogus sha) keeps `error_code == STATUS_SURFACE_REF_UNREADABLE` and is not the subtype.
- NFR-001: on a healthy remote-only-then-branched read, monkeypatch-count `ref_names_object` calls == 0.

### Subtask T011 – Relay, ADR, changelog

- `tests/runtime/next/test_board_query_read_door_7507.py`: add one case that the `next` board query relays `STATUS_SURFACE_REF_REMOTE_ONLY` verbatim as `error_code` (no code change expected in `runtime_bridge_query.py`; if a change is needed, stop and report — it is outside owned files).
- ADR `docs/adr/4.x/2026-11-06-2-one-status-read-contract.md`: append `## Amendment 2026-11-20: a remote-only branch is a typed refusal (#5287)` — a branch with no local head raises `StatusSurfaceRefRemoteOnly` (`STATUS_SURFACE_REF_REMOTE_ONLY`), a subtype of the unreadable-ref error, carrying the canonical remedy from `mission_runtime.coord_remedy`; classified only after a failed read (NFR-001 unchanged); the door still never reads a remote-tracking ref (a remote-tracking source is #7408, under its own amendment).
- `docs/changelog/unreleased/5287.fixed.md`: one user-facing entry (follow `docs/changelog/unreleased/README.md` style rules).

## Test Strategy

```bash
.venv/bin/python -m pytest tests/status/test_read_surface_remote_only_5287.py tests/specify_cli/cli/commands/agent/test_tasks_status_remote_only_5287.py tests/status/test_read_surface_door.py tests/status/test_status_read_matrix.py tests/coordination/test_status_ref_reader.py tests/specify_cli/cli/commands/agent/test_tasks_status_cmd_seam.py tests/specify_cli/cli/commands/agent/test_agent_status_surface_refusals.py tests/runtime/next/test_board_query_read_door_7507.py tests/specify_cli/upgrade/test_backfill_merged_at_migration.py -q -n auto --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_status_read_single_door.py tests/architectural/test_layer_rules.py tests/architectural/test_remote_contact_owner.py tests/architectural/test_no_legacy_terminology.py -q
make test-fast
```

## Definition of Done

- T007 red first, then green; positive control green.
- Subtype raised at both ref sources; corrupt local ref unchanged; no added subprocess on success.
- ADR amendment + changelog fragment; gates green; ruff/format/mypy clean.

## Risks

- Tests that assert `type(exc) is StatusSurfaceRefUnreadable` would break; grep and judge.
- `test_status_read_single_door.py` scans for legacy reads; the new helper must not be a new legacy read (it only calls `ref_names_object`).

## Reviewer Guidance

Confirm no remote-tracking ref is ever read as status; confirm classification is only on the failure path; confirm R2 (#7449) untouched.
