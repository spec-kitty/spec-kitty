---
work_package_id: WP02
title: 'Commit router resolves the holder through the seam (#7551, #7607)'
dependencies: [WP01]
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-011
- FR-012
- SC-001
- SC-003
- C-007
subtasks: [T005, T006, T007, T008, T009]
agent: claude
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/coordination/test_commit_router_settled_holder.py
- tests/specify_cli/cli/commands/test_spec_commit_settled.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/coordination/commit_router.py
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/cli/commands/spec_commit_cmd.py
- tests/coordination/test_commit_router_settled_holder.py
- tests/specify_cli/cli/commands/test_spec_commit_settled.py
role: implementer
---

# WP02 — Commit router resolves the holder through the seam (#7551, #7607)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

After settlement, `spec-kitty spec-commit` lands a tracer, a decision record and a WP's
`baseline-tests.json` on the topic branch whether it is run from the coordination worktree or from the
repository root checkout; a file that exists only at the root path is refused (never copied) with the
holding worktree named; coordination status files are committed under the status lock (FR-002,
FR-003, FR-004, FR-011, FR-012; #7551, #7607).

## Context (read `research/code-grounding.md` §3 first)

- Live failure today (coordination-worktree cwd):
  `spec-commit kitty-specs/<slug>/baseline-tests.json` → `WRONG_SURFACE`: "Artifact(s) not present at
  resolved placement (kitty/mission-…, worktree=<repo root>)". From the root cwd with the file at the
  root path: `safe_commit: worktree <root> HEAD is 'main', expected 'kitty/mission-…'. Run git -C <root>
  checkout kitty/mission-… first.` — git refuses that checkout (the coordination worktree holds it).
- Mechanism: `spec_commit_cmd._current_repo_root` folds cwd to the root (`find_repo_root`), relative
  args are joined to the root (`kernel/resolution.py::resolve_commit_path`), and
  `commit_router._primary_commit_root` (≈ line 1160) keeps the root unless every file already lies in
  the holder (raw `checkout_holding_branch`, the one probe that bypasses the seam). Then
  `_any_path_absent` → `no_op_wrong_surface`.
- Settlement makes `coordination_branch == mission_branch`, so `_resolve_group_placement`'s
  `use_coord = routes_through_coordination(topology) and placement.ref != primary_target` is False for
  every kind. **Keep that rule** (decision `01M78GRZDX410TZ1V8H1ZVC1EM`: routing by topology+kind
  regresses PUBLISHED/landed Missions). Its side effect: `_coord_status_locks(..., use_coord=False)`
  skips the #5353 lock (#7607).
- `_translate_to_owning_surface(repo_root, rel, mission_slug=, owned=, write_dirs=)` (≈ line 1577)
  already maps a root-relative Mission path to `write_dir(kind).path / <mission-relative tail>` via
  `kind_for_mission_file` and `_mission_relative_subpath` — reuse it; never compose
  `holder / "kitty-specs" / slug` (FUNCTIONAL_FS_BYPASS in `test_single_mission_surface_resolver.py`).
- WP01 made `placement_seam(...).write_dir(kind).surface_root` the containing checkout.

Implement with: `spec-kitty agent action implement WP02 --agent claude --mission settled-placement-surface-01M78GR4`

## Branch Strategy

Base and merge target: `fix/7546-settled-placement-surface`; `single_branch`, sequential, no lane worktree.

### Subtask T005: Red — settled spec-commit scenarios through the real CLI

**Steps**:
1. Create `tests/specify_cli/cli/commands/test_spec_commit_settled.py` on the real fixture
   (`make_default_mission(tmp_path, THREE_LANES)` + `run_finalize`; also test `standing_on="dev"` via
   parametrize). Drive the CLI the way users do: a `subprocess.run([sys.executable, "-m",
   "specify_cli", "spec-commit", …], cwd=…)` or typer `CliRunner` with `monkeypatch.chdir` — whichever
   the neighbouring `tests/specify_cli/cli/commands/test_spec_commit*.py` tests use (match them).
   Scenarios (each asserts the commit is on `m.topic` via `git log -1 --format=%s <topic>` /
   `git show <topic>:<path>`, and the root branch tip did not move):
   - (a) coord-worktree cwd, relative `kitty-specs/<slug>/traces/tooling-friction.md` (TRACER_FILE);
   - (b) coord-worktree cwd, relative `kitty-specs/<slug>/tasks/WP01-work/baseline-tests.json` (or the
     WP task dir the fixture uses; WORK_PACKAGE_TASK);
   - (c) coord-worktree cwd, a decision record under `kitty-specs/<slug>/decisions/` (DECISION_LOG);
   - (d) root cwd, same relative path for a file that exists only in the coordination worktree;
   - (e) root-only copy: file written at `<root>/kitty-specs/<slug>/traces/stray.md` and absent in the
     coordination worktree → non-zero exit, `WRONG_SURFACE` reason unchanged, message names the
     coordination worktree path, and the file was NOT copied into the coordination worktree;
   - (f) control: absolute coord path from the root (works today — keep green).
   - Also #5501 re-check: the decision/trace/status paths of a mixed batch are each reported committed.
2. Create `tests/coordination/test_commit_router_settled_holder.py` (in-process `commit_for_mission`):
   - status lock: spy `_hold_coord_status_dir` (or `coord_status_lock`) and commit the coordination
     `status.json` with `kind=STATUS_STATE`; assert the lock was taken (#7607). Control: a
     `single_branch` Mission's status commit at the root does NOT take it (unchanged behaviour).
3. Run: (a)–(e) and the lock test must fail now; (f) and controls pass. Commit the tests alone:
   `test(coordination): pin spec-commit and status lock on a settled default Mission (#7551, #7607)`.

### Subtask T006: `_primary_commit_root` delegates to the seam

**Steps**:
1. Replace the body: the checkout is `placement_seam(repo_root, mission_slug).write_dir(kind).surface_root`
   for the group's `kind` (thread `mission_slug` and `kind` from `_commit_partition_group`, which has
   both). Keep the owned arm (`owned.owned_root`) as is. Remove the raw `checkout_holding_branch`
   import if unused.
2. Guard: if `write_dir` raises a typed seam error, let it propagate exactly like the COORD arm's
   `_OwningSurfaceRefused` path does (look at how the COORD arm builds a refused `SurfaceOutcome`) —
   do not swallow.

### Subtask T007: Re-anchor absent root paths; refuse a root-only copy

**Steps**:
1. In the PRIMARY (`not use_coord`) arm, after resolving `worktree_root`: when `worktree_root` is not
   `repo_root`, map each file `f` that lies under `repo_root` but not under `worktree_root`:
   - if `f` does not exist: re-express via `_translate_to_owning_surface(repo_root, f.relative_to(repo_root), …)`
     (memoise `write_dirs` per batch as that helper expects);
   - if `f` exists at the root path and its translated counterpart does not: refuse the group with the
     existing `WRONG_SURFACE` per-path reason and a diagnostic naming the translated holder path and
     the holding checkout ("…exists only in the repository root checkout; this Mission's files live in
     <holder>. Move it there and re-run."). Do not copy.
   - if both exist: commit the holder copy (the root copy is a stray; mention it in the diagnostic only
     if the commit is unchanged — keep it simple).
2. Keep helper functions small (≤ 15 complexity); extract a `_reanchor_primary_paths(...)` helper with
   its own unit tests in `test_commit_router_settled_holder.py`.

### Subtask T008: Status lock on the holder checkout (#7607)

**Steps**: `_coord_status_locks` engages when `use_coord` **or** (`owned is None` and
`worktree_root.resolve() != repo_root.resolve()`). Pass `owned` (or a precomputed bool) from
`_safe_commit_group`. Update the docstring (settled default Missions commit coordination status in the
holder with `use_coord` False). Do not change `use_coord`.

### Subtask T009: `SafeCommitHeadMismatch` remedy names the holder

**Steps**: in `src/specify_cli/git/commit_helpers.py` (≈ line 188) where the HEAD-mismatch message says
"Run `git -C <root> checkout <ref>` first": when another worktree already holds `<ref>` (use the
existing `specify_cli.status.checkout_holding_branch(repo_root, ref)` read helper, or `git worktree list
--porcelain` through the module's existing git runner), say instead "'<ref>' is checked out in <holder>;
run the command from there (or pass a path inside it)". Message text only — same exception type, same
code (decision `01M78GS9KQZAMG3Y0YC53ER1KE`). Add a unit test in `test_commit_router_settled_holder.py`
(or the existing commit_helpers test module if one covers this message — check `grep -rl SafeCommitHeadMismatch tests`; if it is outside this WP's owned files, record a one-line rationale for the out-of-map edit).

## Definition of Done

- T005 tests committed red first; all green after T006–T009.
- `pytest tests/coordination tests/specify_cli/cli/commands/test_spec_commit*.py tests/specify_cli/cli/commands/test_safe_commit*.py -q` green.
- Gates: `pytest tests/architectural/test_write_surface_placement_guard.py tests/architectural/test_no_write_side_rederivation.py tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_commit_scope_owner.py tests/architectural/test_safe_commit_import_boundary.py tests/architectural/test_topology_inference_retired.py -q` green.
- ruff/format/mypy clean; complexity ≤ 15; mark-status T005–T009 done.

## Risks

- PUBLISHED/landed default Missions: `write_dir(kind).surface_root` there is the root (the topic holder
  is gone) — add one control asserting a landed fixture is unchanged if a cheap one exists; otherwise
  rely on existing PUBLISHED tests in `tests/coordination`.
- Do not route through coordination staging; do not change `_group_files_by_partition`.

## Reviewer Guidance

Check: no copy path; reason codes unchanged; the lock predicate cannot fire for owned or root commits;
the re-anchor uses `_translate_to_owning_surface` (no new path composition).
