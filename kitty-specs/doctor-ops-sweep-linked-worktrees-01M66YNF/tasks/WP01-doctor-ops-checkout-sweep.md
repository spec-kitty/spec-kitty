---
work_package_id: WP01
title: Sweep Op records across every checkout
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6661-doctor-ops-sweep-linked-worktrees
merge_target_branch: issue-6661-doctor-ops-sweep-linked-worktrees
branch_strategy: Planning artifacts for this mission were generated on issue-6661-doctor-ops-sweep-linked-worktrees. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6661-doctor-ops-sweep-linked-worktrees unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Fix
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/doctor/
create_intent:
- tests/specify_cli/invocation/test_doctor_ops_worktrees.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/invocation/op_custody.py
- src/specify_cli/doctor/ops.py
- src/specify_cli/cli/commands/doctor.py
- src/specify_cli/session_presence/open_ops.py
- tests/specify_cli/invocation/test_doctor_ops.py
- tests/specify_cli/invocation/test_doctor_ops_worktrees.py
- tests/specify_cli/session_presence/test_open_ops.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Sweep Op records across every checkout

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objectives & Success Criteria

`spec-kitty doctor ops` must see and sweep Op records in **every** checkout of the
repository, because Op records have been written in the invoking checkout since
#6564/#6664. Today it reads one directory, `<project root>/kitty-ops`, so an Op
opened in a linked worktree is invisible and `--close-stale` never closes it.

Done when:

- `doctor ops` lists an open Op that lives in a linked worktree, from the root
  checkout and from inside the worktree, and exits 1 (SC-001).
- `doctor ops --close-stale --threshold 0` closes stale Ops in the root checkout
  and in linked worktrees in one run, each closure appended to the closure spine of
  the checkout that owns the record, and a second run reports none (SC-002).
- The session-start/stop reminder still spawns zero git subprocesses and still reads
  the root checkout only, pinned by a test (SC-003, C-002).
- One `doctor ops` run spawns exactly one `git worktree list` (SC-004, NFR-001).
- A non-git directory, a repository without worktrees, and a failing
  `git worktree list` all behave exactly as today (SC-005).

## Context & Constraints

Read first: `kitty-specs/doctor-ops-sweep-linked-worktrees-01M66YNF/spec.md`
(requirements), `plan.md` (design detail and IC-01..IC-03), `research.md`
(code survey and decisions D1–D5), and `.kittify/charter/charter.md`.

The state of the code before this WP:

- `src/specify_cli/doctor/ops.py` — `list_orphan_ops(repo_root)` globs
  `<repo_root>/kitty-ops/*.jsonl` and reads the closure spine via
  `closed_invocation_ids(repo_root)`. `close_stale_ops` builds one
  `ProfileInvocationExecutor(repo_root, propagator=...)` with no `record_root`.
- `src/specify_cli/invocation/op_custody.py` — `_repository_checkouts(project_root)`
  already yields every checkout from `git worktree list --porcelain`, resolved;
  `locate_op_record_root` is its only caller.
- `src/specify_cli/invocation/executor.py` — `ProfileInvocationExecutor(repo_root,
  ..., record_root=None)`; `record_root` owns the writer, the closure spine, the
  auto-commit and the doctor-sweep closed-id cache, while governance (profile
  registry, glossary chokepoint) stays on `repo_root`.
- `src/specify_cli/cli/commands/doctor.py` — `ops` renders
  `path.relative_to(repo_root)`, which raises for a record outside the root.
- `src/specify_cli/session_presence/open_ops.py` — calls `list_orphan_ops` on every
  session boundary under a "no git calls, < 0.5 s at 1,000 files" contract.

Hard constraints:

- **Do not** add `git worktree list` to `list_orphan_ops` or to anything on the
  session-presence path (C-002).
- **Do not** mutate a per-record `kitty-ops/<id>.jsonl`; the sweep closes on the
  append-only spine only, through `complete_invocation` (C-004, ADR/#4397).
- **Do not** change the `doctor ops --json` payload shape or the sweep report's
  entry keys (C-001), and add no new flag, config key or transport (C-003).
- **Do not** reopen the mission-step half (#6664).

## Branch Strategy

- **Strategy**: planning artifacts were generated on
  `issue-6661-doctor-ops-sweep-linked-worktrees`; this WP implements in the write
  checkout on that branch.
- **Planning base branch**: `issue-6661-doctor-ops-sweep-linked-worktrees`
- **Merge target branch**: `issue-6661-doctor-ops-sweep-linked-worktrees`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: a worktree Op is listed

- **Purpose**: Prove the defect through the pre-existing entry point before touching
  production code.
- **Steps**: Create `tests/specify_cli/invocation/test_doctor_ops_worktrees.py`
  (module marks: `unit`, `fast`, `non_sandbox`). Build a real repository with the
  helpers in `tests/specify_cli/invocation/_op_git.py` (`run_git`,
  `track_op_record_on_current_branch`), add a linked worktree
  (`git worktree add -b topic <lane>`), and write a started-only record directly at
  `<lane>/kitty-ops/<ULID>.jsonl` (do **not** open it through the CLI — that would
  fail on custody before reaching the sweep). Invoke the CLI with
  `typer.testing.CliRunner` and `monkeypatch.chdir(<root>)`. Assert the payload is
  `[{"path": "../lane/kitty-ops/<id>.jsonl"}]` and `exit_code == 1`.
- **Files**: `tests/specify_cli/invocation/test_doctor_ops_worktrees.py`
- **Parallel?**: no — this is the red anchor; commit it alone.
- **Notes**: Run it on the untouched tree and record the RED output (`[]`, exit 0) in
  the WP history. A test that passes before the fix is not a repro.

### Subtask T002 – Red-first: the sweep closes it in its own checkout

- **Purpose**: Pin the write half — where the closure lands.
- **Steps**: In the same module, seed one stale Op in the root checkout and one in
  the linked worktree, run `doctor ops --close-stale --threshold 0 --json`, and
  assert: both entries report `closed_abandoned`; the root
  `kitty-ops/op-closures.jsonl` contains only the root invocation id; the lane's
  contains only the lane's; and `doctor ops --json` afterwards reports
  `[]` with exit 0.
- **Files**: `tests/specify_cli/invocation/test_doctor_ops_worktrees.py`
- **Parallel?**: no — shares the fixture module with T001.
- **Notes**: The lane needs a non-protected branch and a committed seed so the
  auto-commit is not refused; if a spine commit is refused on that platform, assert
  the existing `not_committed:` / `skipped:` vocabulary rather than a commit.

### Subtask T003 – One public checkout enumeration

- **Purpose**: Give the checkout set a single owner (FR-006).
- **Steps**: Rename `_repository_checkouts` to `repository_checkouts` in
  `src/specify_cli/invocation/op_custody.py`, export it in `__all__`, document it as
  the shared enumeration ("every checkout of the project's repository, from
  `git worktree list --porcelain`; empty when git is unavailable"), and update its
  caller in `locate_op_record_root`. Behavior must not change.
- **Files**: `src/specify_cli/invocation/op_custody.py`
- **Parallel?**: no.
- **Notes**: Keep the `_git_lines` failure contract (returns `None` → no checkouts).
  Do not add a second walk anywhere else.

### Subtask T004 – Doctor enumerates and sweeps every checkout

- **Purpose**: The fix (FR-001, FR-002, NFR-001..NFR-003).
- **Steps**:
  1. Add a module-private `_checkouts(repo_root) -> list[Path]`: `[repo_root, *repository_checkouts(repo_root)]`,
     de-duplicated by `Path.resolve()`, order preserved (project root first, then
     `git worktree list` order).
  2. Add `list_orphan_ops_across_checkouts(repo_root) -> list[Path]`: concatenate
     `list_orphan_ops(checkout)` for each entry of `_checkouts(repo_root)`.
  3. In `close_stale_ops`, enumerate with `list_orphan_ops_across_checkouts` and keep
     a `dict[Path, ProfileInvocationExecutor]` keyed by the record's owning checkout
     (`record.parent.parent`, resolved), constructing each with
     `record_root=<checkout>` and the same `InvocationSaaSPropagator(repo_root)`.
     Everything else in the loop (age, `parse_warning`, staleness, `already_closed`,
     per-op `error`, `commit` vocabulary) stays byte-for-byte the same in behavior.
- **Files**: `src/specify_cli/doctor/ops.py`
- **Parallel?**: no.
- **Notes**: One `git worktree list` per call, never per record (NFR-001). A failing
  checkout or a failing close must not abort the sweep (NFR-002). Keep the docstrings
  truthful: `list_orphan_ops` is the single-checkout scan used by session presence;
  the sweep uses the checkout-aware one.

### Subtask T005 – Root-relative listing paths

- **Purpose**: Report which checkout holds each record without changing the payload
  shape (FR-003, C-001).
- **Steps**: In `src/specify_cli/cli/commands/doctor.py`, replace
  `path.relative_to(repo_root)` with a helper that returns
  `Path(os.path.relpath(path, repo_root)).as_posix()` (falling back to
  `path.as_posix()` if `os.path.relpath` raises `ValueError`, e.g. a different
  Windows drive). Use it in both the `--json` payload and the table.
- **Files**: `src/specify_cli/cli/commands/doctor.py`
- **Parallel?**: no.
- **Notes**: Root records must stay exactly `kitty-ops/<id>.jsonl` (an existing test
  asserts it). No absolute paths in output. The sweep's human output needs no change:
  the invocation id already identifies the record, and the closure commit lands on
  the owning checkout's branch.

### Subtask T006 – Pin the session-presence boundary

- **Purpose**: Keep the hot path single-checkout and git-free (FR-004, C-002, SC-003).
- **Steps**: Extend the `session_presence/open_ops.py` module docstring to say the
  scan is deliberately the project root checkout only (the doctor sweep is the
  repository-wide surface). Add a test in
  `tests/specify_cli/session_presence/test_open_ops.py` that patches
  `specify_cli.invocation.op_custody._git_lines` (or `subprocess.run`) to raise and
  asserts `render_open_ops_section` still returns its normal output — and that a
  worktree Op is not listed.
- **Files**: `src/specify_cli/session_presence/open_ops.py`,
  `tests/specify_cli/session_presence/test_open_ops.py`
- **Parallel?**: yes, once T003/T004 have landed.
- **Notes**: Do not widen the scan. If you feel the urge to list worktree Ops here,
  stop: that is a different decision with its own latency budget.

### Subtask T007 – Degraded paths, ordering and cost

- **Purpose**: Prove the contract in the edges (FR-005, NFR-001, NFR-003, SC-004,
  SC-005).
- **Steps**: In `tests/specify_cli/invocation/test_doctor_ops.py` add:
  (a) a non-git directory behaves as today (`list_orphan_ops_across_checkouts` equals
  the single-checkout result); (b) a monkeypatched `repository_checkouts` returning
  nothing leaves the result unchanged; (c) ordering is root first, then git order,
  with file-name order inside a checkout; (d) a counting wrapper around the git call
  shows exactly one `git worktree list` per `doctor ops` run and per
  `close_stale_ops` call. Keep the existing tests untouched and green.
- **Files**: `tests/specify_cli/invocation/test_doctor_ops.py`
- **Parallel?**: yes, after T004.
- **Notes**: Count the git call at the seam the production code uses (patch
  `op_custody._git_lines` or `subprocess.run` in that module) so the assertion is
  about behavior, not an implementation detail.

## Test Strategy

Targeted runs only; never the full heavy suite.

```bash
uv run pytest tests/specify_cli/invocation/test_doctor_ops_worktrees.py -q
uv run pytest tests/specify_cli/invocation/test_doctor_ops.py tests/specify_cli/invocation/test_op_custody.py -q
uv run pytest tests/specify_cli/session_presence/test_open_ops.py tests/specify_cli/session_presence -q
uv run ruff check src/specify_cli/doctor src/specify_cli/invocation/op_custody.py src/specify_cli/cli/commands/doctor.py src/specify_cli/session_presence tests/specify_cli/invocation tests/specify_cli/session_presence
uv run ruff format --check <changed files>
uv run mypy src/specify_cli/doctor/ops.py src/specify_cli/invocation/op_custody.py src/specify_cli/cli/commands/doctor.py src/specify_cli/session_presence/open_ops.py
```

Fixtures seed records on disk (never through the CLI) and use a throwaway git
identity, so no test depends on the host's git config.

## Risks & Mitigations

- **The single-checkout scan quietly widens** → `list_orphan_ops` is untouched, its
  docstring says so, and T006 pins zero git calls.
- **Every closure lands in the root anyway** (one executor, no `record_root`) → T002
  asserts each spine holds exactly its own closure.
- **`relative_to` crashes on the first out-of-root record** → T005 covers the table
  and `--json` path; the existing root-shaped test guards the unchanged case.
- **Git cost per record** → T007 counts `git worktree list` calls.
- **A stale `git worktree list` entry** (deleted checkout) → contributes nothing
  because there is no `kitty-ops/`; never pruned, never raised.

## Review Guidance

- Confirm the red commits exist and fail for the reported reason before the fix
  commit, not for an unrelated setup error.
- Confirm `list_orphan_ops` (and `closed_invocation_ids`) are still called with one
  checkout on the session-presence path.
- Confirm the sweep builds an executor whose `record_root` is the record's owning
  checkout, and that `repo_root` still owns the profile registry and the propagator.
- Confirm no per-record file is mutated and no new git walk appears outside
  `op_custody`.
- Confirm the root-only case is behavior- and output-identical to before.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
