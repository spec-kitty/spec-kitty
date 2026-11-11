---
work_package_id: WP02
title: The decisions runtime lock is never dirt and never committed (#7498)
dependencies: []
requirement_refs:
- FR-008
- FR-009
- FR-010
- FR-011
- NFR-002
- NFR-003
- C-001
- C-002
- SC-003
planning_base_branch: fix/7549-doctor-scope-lock-hygiene
merge_target_branch: fix/7549-doctor-scope-lock-hygiene
branch_strategy: Planning artifacts for this mission were generated on fix/7549-doctor-scope-lock-hygiene. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7549-doctor-scope-lock-hygiene unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
phase: Phase 1 - Bug fixes
history:
- at: '2026-11-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/decisions/test_runtime_lock_hygiene_7498.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/lock.py
- src/specify_cli/git/commit_helpers.py
- src/specify_cli/git/ref_advance.py
- tests/decisions/test_runtime_lock_hygiene_7498.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The decisions runtime lock is never dirt and never committed (#7498)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according
to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item; record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

## Objectives & Success Criteria

- FR-008: after a real decision write, `kitty-specs/<m>/decisions/index.json.lock` is not listed by `git status` in the
  repository root checkout, a coordination worktree or a lane worktree, in a fixture with no `*.lock` ignore rule.
- FR-009: a `safe_commit` (so `spec-commit`, `safe-commit`, every Mission commit) whose requested paths include the lock
  refuses with `SafeCommitPathPolicyError` (`SAFE_COMMIT_PATH_POLICY`) before any index mutation; the same request
  without the lock commits (positive control).
- FR-010: the owned `index_only_removals` route (`agent decision repair-runtime-lock`) still commits the lock's removal.
- FR-011: reset-obstruction lines describe state in words ("untracked" / "ignored by git"), not `??`/`!!`.
- SC-003.

## Context & Constraints

- Read [plan.md](../plan.md) D-8..D-11 and [research/code-grounding.md](../research/code-grounding.md) §2.
- C-001: never unlink or truncate a lock file (kernel `locks.py` G3). No raw OS lock calls
  (`tests/architectural/test_lock_primitive_ban.py`).
- `git/ref_advance.py` must keep zero `specify_cli` imports.
- Reuse `coordination.coherence.is_decisions_runtime_lock` for the predicate and `decisions.lock.LOCK_FILENAME` for the
  name; do not add module-level filename lists (`test_exemption_registry_ratchet.py`).
- C-002: no consolidation/rollback change.

## Branch Strategy

- **Planning base branch**: `fix/7549-doctor-scope-lock-hygiene` (via the Mission branch)
- **Merge target branch**: `fix/7549-doctor-scope-lock-hygiene`
- Execution workspaces are allocated per computed lane from `lanes.json`; run
  `spec-kitty agent action implement WP02 --agent claude --mission doctor-scope-lock-hygiene-01M75NSF`.

## Subtasks & Detailed Guidance

### T006 – Red tests first (separate commit)

New `tests/decisions/test_runtime_lock_hygiene_7498.py` (real git repos in `tmp_path`, no `*.lock` rule in `.gitignore`):
1. Take the decisions lock through the real owner (`decisions.lock.decisions_lock(lock_path(mission_dir), ...)`) or a real
   `decision open` through the CLI if a fixture exists; after release, `git status --porcelain --untracked-files=all` in
   the root checkout lists no `index.json.lock`.
2. Same, with a linked worktree (`git worktree add`) standing in for a coordination worktree and one for a lane worktree:
   a lock written in either is not listed by that worktree's `git status`.
3. `safe_commit(...)` with paths `(spec.md, decisions/index.json.lock)` → raises `SafeCommitPathPolicyError` naming the
   lock; HEAD and the index unchanged. Positive control: `(spec.md,)` commits.
4. End to end through the CLI: `spec-kitty spec-commit <dir>/spec.md <dir>/decisions/index.json.lock --mission <m>`
   (via `CliRunner` on the real app, or the existing spec-commit test fixture) exits non-zero and commits nothing.
5. `index_only_removals` route: use the existing repair-runtime-lock test (find it with
   `grep -rln repair_runtime_lock tests`) as the ratchet; run it.
6. `ref_advance` label: an untracked file that obstructs a tracked path → refusal line contains "untracked" and no `?? `.

Commit: `test(decisions): red tests for decisions runtime lock hygiene (#7498)`.

### T007 – Exclusion at the lock owner

- In `decisions/lock.py`, before `machine_file_lock` in `decisions_lock`, call a private `_ensure_runtime_lock_excluded(held_lock)`
  that appends `**/kitty-specs/*/decisions/index.json.lock` (built from `LOCK_FILENAME`) via
  `core.git_ops.exclude_from_git_index(held_lock.parent, [...])`. `git_exclude_file` resolves the common dir, so a lock in
  any worktree reaches the shared file. Best-effort: never raise (wrap `OSError`/`GitTopologyError`); the commit backstop
  is the guarantee.
- NFR-002: memoize per common-dir within the process (a module-level `set` of resolved exclude paths is fine).

### T008 – Commit backstop

- `preflight_commit` (`git/commit_helpers.py`), step 6a: after the `.worktrees/` check, refuse any normalized path for
  which `is_decisions_runtime_lock` holds, unless it is in an `index_only_removals` set passed down from `safe_commit`
  (add a keyword-only `index_only_removals: frozenset[str] = frozenset()` parameter). Extend `SafeCommitPathPolicyError`
  with a `reason` so the message for the lock reads: "refusing to stage the decisions runtime lock <path>: it is Spec
  Kitty's runtime lock and is never committed. Remove it from the paths you pass." Keep the existing `.worktrees/` text
  byte-identical (default reason).

### T009 – Obstruction label

- `ref_advance._dirty_reason`: for untracked/ignored obstruction lines use `f"{entry.path} (untracked; …)"` /
  `f"{entry.path} (ignored by git; …)"` instead of `entry.display()`. Check any test pinning the old text and update.

### T010 – Topology pins

- #7498 gap 1/2 are covered by T006 cases 2 (lane and coordination worktrees share the common-dir exclude) and 3/4 (no
  commit route can stage it). Record in the WP history that the lane dirty gates
  (`_check_uncommitted_worktree_changes`, `_validate_worktree_clean`, move-task auto-commit) read `git status` without
  `--ignored`, so an excluded lock never reaches them.

## Test Strategy (targeted; never `make test-full`)

```bash
uv run --frozen pytest tests/decisions/ tests/specify_cli/decisions/ -q
uv run --frozen pytest $(grep -rl "SafeCommitPathPolicyError\|preflight_commit\|_RESET_OBSTRUCTION_NOTE\|would be overwritten by reset" tests) -q
uv run --frozen pytest tests/architectural/test_lock_primitive_ban.py tests/architectural/test_exemption_registry_ratchet.py -q
```

## Definition of Done

- T006 red commit precedes the fix; all listed tests green; ruff/format/mypy clean on changed files; complexity ≤ 15.

## Risks

- Tests elsewhere that commit a lock on purpose (search `index.json.lock` in tests) — they must pass the lock through
  `index_only_removals` or be re-pinned.

## Reviewer Guidance

- Verify no unlink/truncate of the lock anywhere; verify the refusal fires before any index mutation.
