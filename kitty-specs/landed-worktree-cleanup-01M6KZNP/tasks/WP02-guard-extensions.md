---
work_package_id: WP02
title: 'Destructive guard: no-force removal and LANDED branch intent'
dependencies: []
requirement_refs:
- C-002
- FR-003
- FR-004
- NFR-001
planning_base_branch: issue-7173-landed-worktree-cleanup
merge_target_branch: issue-7173-landed-worktree-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-7173-landed-worktree-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7173-landed-worktree-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-landed-worktree-cleanup-01M6KZNP
base_commit: 18556aadd0acd448f91c53ddd870e606d3feb56a
created_at: '2026-11-04T23:49:55.961808+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 0 - Foundation
history:
- at: '2026-11-04T19:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- tests/specify_cli/git/test_destructive_guard_landed.py
execution_mode: code_change
owned_files:
- src/specify_cli/git/destructive_guard.py
- tests/specify_cli/git/test_destructive_guard_landed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Destructive guard: no-force removal and LANDED branch intent

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback; record changes with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

- `guarded_worktree_remove(..., force: bool = True)`: with `force=False` it runs the **same** clean proof (`assert_worktree_clean(..., treat_untracked_as_dirty=True)`) and then a plain `git worktree remove -- <path>` (no `--force`). Existing callers are unchanged (default `True`).
- `guarded_branch_delete(..., operator_intent=LANDED_INTENT)`: deletes the branch; when its commits exist on no other ref it first records the tip under `discarded_ref(...)` (same mechanism as `DISCARD_INTENT`) and returns that tip; if the record cannot be written, it refuses (`DESTRUCTIVE_OP_ONLY_COPY`) and deletes nothing.
- Operator rulings (Decision Moments `plan.guard.worktree_remove_mode`, `plan.guard.landed_branch_delete`): never `--force` for the prune; branch tips of pruned branches stay recoverable.

## Context & Constraints

- `src/specify_cli/git/destructive_guard.py` is the ONE chokepoint (module docstring; `tests/architectural/test_destructive_op_routing.py`, no allowlist). Destructive literals may only live in this module and `git/ref_advance.py`.
- **Do not** add a caller of the new intent outside the guard in this WP. WP03 adds the single production caller and updates the `_OPERATOR_INTENT_CALLERS` pin (a set-equality check) in the same change.
- Keep the module git-plumbing-pure (no `specify_cli` application imports).
- The `operator_intent` validation currently raises `ValueError` for unknown values; extend the accepted set with `LANDED_INTENT = "landed"` and document it like the other two constants (what it means, who may pass it: only `workspace/landed_worktrees.py::prune_landed` after the absorption proof).

## Branch Strategy

- **Planning base branch**: `issue-7173-landed-worktree-cleanup`
- **Merge target branch**: `issue-7173-landed-worktree-cleanup`

Run `spec-kitty agent action implement WP02 --agent claude --mission landed-worktree-cleanup-01M6KZNP` and work in the printed workspace.

## Subtasks & Detailed Guidance

### Subtask T005 – No-force removal mode

- **Steps**:
  1. Add keyword `force: bool = True` to `guarded_worktree_remove`.
  2. Add a guard-internal `_remove_worktree(worktree, env, *, force: bool)`; keep `_remove_worktree_force` behaviour for `force=True` (you may refactor it into the new helper, keeping the literal `["worktree", "remove", "--force", ...]` inside this module).
  3. With `force=False` git itself refuses a locked worktree and a dirty one; surface that refusal as `DestructiveOpRefused` with a new error code constant `WORKTREE_REMOVE_REFUSED_BY_GIT` (stderr in `dirty_entries` or remediation), not a bare `RuntimeError`, so callers can report it per worktree.
  4. `retain=True` path: honour `force` the same way.
- **Notes**: Plain `git worktree remove` deletes ignored files (e.g. `.venv`) — this is intended; confirm with a test. Keep complexity ≤ 15.

### Subtask T006 – `LANDED_INTENT`

- **Steps**:
  1. `LANDED_INTENT = "landed"` constant with a docstring.
  2. In `guarded_branch_delete`: `operator_intent == LANDED_INTENT` → reuse `_discard_branch_keeping_tip` (it records the tip under `discarded_ref` only when commits are unique, then `branch -D`). Return the recorded tip or `None`.
  3. Update the function docstring: three named intents.
- **Notes**: The guard does **not** verify absorption itself (it is plumbing-pure); the caller proves it. Say so in the docstring.

### Subtask T007 – Tests

- **File**: `tests/specify_cli/git/test_destructive_guard_landed.py` (new; mark `integration`, `git_repo` like neighbouring guard tests in `tests/specify_cli/git/test_destructive_guard.py`).
- **Cases**:
  - `force=False` on a clean worktree removes it; the git command run has no `--force` (assert via a monkeypatched `_run_git` spy or by locking: see next).
  - `force=False` on a **locked** clean worktree → `DestructiveOpRefused(WORKTREE_REMOVE_REFUSED_BY_GIT)`, worktree still present (positive control: same fixture unlocked is removed).
  - `force=False` with an untracked file → refused by the guard's own proof; worktree and file intact.
  - `force=False` with only an ignored `.venv/` dir → removed.
  - `LANDED_INTENT` on a branch whose commits are on `origin/...` (not unique) → deleted, returns `None`, no discarded ref written.
  - `LANDED_INTENT` on a branch with unique commits → `refs/spec-kitty/discarded/<b>` holds the old tip, branch gone, return value equals that tip; `git branch <b> <tip>` recreates it.
  - Unknown intent still raises `ValueError`.
- Run existing guard tests unchanged: `tests/specify_cli/git/test_destructive_guard.py`, `tests/architectural/test_destructive_op_routing.py`.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/git/test_destructive_guard_landed.py tests/specify_cli/git/test_destructive_guard.py tests/specify_cli/git/test_guarded_site_routing_misc.py tests/architectural/test_destructive_op_routing.py -q
uv run --frozen ruff check src/specify_cli/git/destructive_guard.py tests/specify_cli/git/test_destructive_guard_landed.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/git/destructive_guard.py tests/specify_cli/git/test_destructive_guard_landed.py
uv run --frozen mypy src/specify_cli/git/destructive_guard.py
```

## Risks & Mitigations

- Changing default behaviour of existing callers: default stays `force=True`; no existing call site changes.
- Routing gate: keep the new literal inside the guard module; run the routing test.

## Review Guidance

- No `--force` on the `force=False` path (read the argv).
- Locked worktree is refused, not force-removed.
- LANDED never deletes a branch whose only copy could not be recorded.

## Progress & Status

Record notes with `spec-kitty agent tasks add-history WP02 --note "..."`.
