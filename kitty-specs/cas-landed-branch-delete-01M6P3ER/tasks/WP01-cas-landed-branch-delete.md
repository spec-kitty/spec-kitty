---
work_package_id: WP01
title: Compare-and-swap landed branch delete
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7212-cas-landed-branch-delete
merge_target_branch: issue-7212-cas-landed-branch-delete
branch_strategy: Planning artifacts for this mission were generated on issue-7212-cas-landed-branch-delete. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7212-cas-landed-branch-delete unless the human explicitly redirects the landing branch.
base_branch: issue-7212-cas-landed-branch-delete
created_at: '2026-11-05T15:05:00.000000+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Core behaviour
history:
- at: '2026-11-05T15:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- docs/changelog/unreleased/7212.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/git/destructive_guard.py
- src/specify_cli/workspace/landed_worktrees.py
- tests/specify_cli/git/test_destructive_guard_landed.py
- tests/specify_cli/workspace/test_landed_worktrees.py
- tests/architectural/test_destructive_op_routing.py
- docs/development/how-to/pr-landing.md
- docs/changelog/unreleased/7212.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7212'
---

# Work Package Prompt: WP01 – Compare-and-swap landed branch delete

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objective

`spec-kitty doctor workspaces --prune` deletes a landed worktree's branch with
`git branch -D` after comparing the branch tip with the assessed tip. The read
and the delete are not atomic: a branch that moves in the window is deleted with
its new commit. Make the delete a single compare-and-swap bound to the assessed
tip, keep every other behaviour unchanged, and pin the invariant in the routing
gate.

Repo-root-relative paths; branch `issue-7212-cas-landed-branch-delete` (stacked
on the open #7196 branch; the touched module does not exist on `main`).

## Context

Read first:

- `kitty-specs/cas-landed-branch-delete-01M6P3ER/spec.md` — FR-001..FR-006,
  edge cases (branch gone, checked out elsewhere, refused after record).
- `kitty-specs/cas-landed-branch-delete-01M6P3ER/research.md` — R2 (the order is
  right, the binding is wrong) and R3 (options rejected, so do not add a second
  `update-ref -d` implementation).
- `kitty-specs/cas-landed-branch-delete-01M6P3ER/contracts/guard-branch-delete-cas.md`
  — the exact guard contract.
- `src/specify_cli/git/ref_advance.py::delete_branch_ref` and its tests
  `tests/git/test_delete_branch_ref.py` — the reuse target (#5570).

Current code (before this WP):

```python
# workspace/landed_worktrees.py
live = branch_tip(repo_root, branch)
if live != tip:
    return False, None, BRANCH_MOVED
recorded = guarded_branch_delete(repo_root, branch, creation_base=None, operator_intent=LANDED_INTENT)

# git/destructive_guard.py :: _discard_branch_keeping_tip
if _unique_commits(...):
    tip = branch_tip(repo_root, branch)   # second, independent read
    _keep_discarded_tip(...)
_git_ok(repo_root, ["branch", "-D", "--", branch])
```

## Branch Strategy

- Planning branch and merge target: `issue-7212-cas-landed-branch-delete`.
- Implementation runs on this branch (single-branch topology, one lane); no
  per-lane worktree is computed for this Mission.
- The PR for this branch targets `issue-7173-landed-worktree-cleanup` until
  #7196 lands, then main. Never push to `main`; never rebase on anything but a
  genuine `CONFLICTING` mergeable state.

## Subtasks

### T001 — Red-first: a branch moved inside the guarded delete is kept

In `tests/specify_cli/workspace/test_landed_worktrees.py`, next to
`test_a_branch_moved_after_removal_is_not_deleted` (which covers the prune's own
fast path), add `test_a_branch_moved_inside_the_delete_is_kept`:

- Use the existing `_land_by_rebase` fixture and `_idle_probe`.
- Monkeypatch `landed_worktrees.guarded_branch_delete` with a wrapper that, on
  the first call, moves the branch to a fresh commit created with
  `git commit-tree` (reached by no other ref, so the keep-record scan sees it as
  unique) and then delegates to the real guard with the same kwargs.
- Assert: the branch still exists at the new commit (`git rev-parse` equals the
  phantom SHA), `prune_landed` returns `removed=True` (the worktree is gone) but
  `branch_deleted=False` and `refusal == landed_worktrees.BRANCH_MOVED`.
- **Positive control on the same fixture shape**: a second test (or a parameter)
  without the move asserts the branch is deleted. The pair must share the
  fixture builder so the negative and positive cases cannot drift.

Run it against the pre-fix tree and record the failure (the branch is gone /
`branch_deleted` is true). Do not weaken the assertion to match the bug.

### T002 — `guarded_branch_delete(..., expected_tip=...)` (CAS under LANDED)

In `src/specify_cli/git/destructive_guard.py`:

- Add keyword-only `expected_tip: str | None = None`.
- Keep the intent validation. Then: `if operator_intent == LANDED_INTENT and
  expected_tip is None: raise ValueError(...)` — before any git call. Update the
  docstring (the mapper's named-intent table stays accurate).
- Under `LANDED_INTENT` (and, generally, whenever `expected_tip` is not `None`):
  1. Resolve the branch; absent → return `None` (unchanged no-op).
  2. If the live tip differs from `expected_tip`, raise
     `DestructiveOpRefused(error_code=BRANCH_TIP_MOVED, ...)` naming both SHAs;
     nothing is read further, nothing is recorded, nothing is deleted.
  3. Run the existing unique-commit scan for `_LOCAL_REF_NAMESPACES`. If the tip
     has no other local branch/tag, write the create-only
     `refs/spec-kitty/discarded/<branch>` record at **`expected_tip`** (not a
     fresh read). A failed record still raises `DESTRUCTIVE_OP_ONLY_COPY` and
     deletes nothing.
  4. Delete with
     `ref_advance.delete_branch_ref(repo_root, branch, expected_tip)`, imported
     from the sibling module already imported by the guard.
  5. Map failures to typed refusals (no raw git error escapes):
     `RefDeleteMismatchError` → `BRANCH_TIP_MOVED`,
     `RefDeleteCheckedOutError` → `BRANCH_CHECKED_OUT`,
     `RefDeleteError` → `BRANCH_DELETE_REFUSED_BY_GIT`.
- Add module constants for the three new codes next to the existing ones, with
  one-line docstrings in the same style.
- Do **not** change the plain, `FORCE_RECREATE_INTENT` or `DISCARD_INTENT`
  paths; they keep `git branch -D` and their current returns/refusals.
- Keep ruff complexity ≤ 15: extract small helpers if needed
  (`_landed_cas_delete`), do not grow `guarded_branch_delete` into a branch
  forest.

### T003 — Guard tests

In `tests/specify_cli/git/test_destructive_guard_landed.py` (real-git style,
mirroring `tests/git/test_delete_branch_ref.py`):

1. `LANDED_INTENT` + matching `expected_tip` deletes the branch and, when the tip
   is unique, returns the recorded SHA under `refs/spec-kitty/discarded/<branch>`
   (existing behaviour kept).
2. `LANDED_INTENT` + stale `expected_tip` (branch moved to a fresh commit)
   raises `DestructiveOpRefused` with `BRANCH_TIP_MOVED`, nothing deleted, and
   the branch still at the moved tip.
3. `LANDED_INTENT` without `expected_tip` raises `ValueError` and the branch is
   untouched.
4. A branch checked out in another worktree raises `BRANCH_CHECKED_OUT` (or the
   existing code path the guard already maps for it) and is not deleted.
5. Non-LANDED paths unchanged: a `None`-intent delete of a unique-commit branch
   still raises `BRANCH_HAS_UNIQUE_COMMITS`; `FORCE_RECREATE_INTENT` still
   deletes.

### T004 — Prune passes the expected tip and maps the refusals

In `src/specify_cli/workspace/landed_worktrees.py`:

- `_delete_landed_branch`: call
  `guarded_branch_delete(repo_root, branch, creation_base=None,
  operator_intent=LANDED_INTENT, expected_tip=tip)`.
- `tip` is `str | None` today. Under `LANDED_INTENT` the guard requires a real
  value: when `tip is None` the branch has no assessed tip to bind to — keep the
  current conservative behaviour (do not delete) rather than passing `None`
  through. State the chosen refusal in the code and in the outcome (a naked
  `False` with no refusal is acceptable only if the branch is already gone).
- Map the guard's new codes onto the existing operator-facing vocabulary:
  `BRANCH_TIP_MOVED` → `BRANCH_MOVED`, `BRANCH_CHECKED_OUT` →
  `Reason.BRANCH_IN_OTHER_WORKTREE.value`. Everything else keeps its code.
- Update the module docstring paragraph that currently says "That delete is not
  compare-and-swap, so the prune re-reads the branch tip ...". It must now say
  the delete itself is the compare-and-swap and the earlier comparison is only a
  fast path.
- Keep the prune's ordering unchanged: re-assess → remove the worktree → delete
  the branch. Do not move the delete before the removal.

### T005 — Routing gate pins the expected tip

In `tests/architectural/test_destructive_op_routing.py`:

- Extend `_operator_intent_callers` (or add a sibling scanner built on the same
  AST helpers, so the gate keeps one scanner per concern) to record whether the
  `guarded_branch_delete(..., operator_intent=...)` call also passes
  `expected_tip`.
- Assert: the LANDED caller
  (`workspace/landed_worktrees.py::_delete_landed_branch`) passes
  `expected_tip`; the force-recreate and discard callers do not need to (and do
  not).
- Add a **non-vacuity** test: a planted source with a LANDED call missing
  `expected_tip` is reported by the same scanner. Keep the census keyed by
  content, no allowlist, and do not weaken any existing assertion.
- If adding a needle for a new argv is unnecessary (the delete goes through
  `ref_advance`, already guard-internal), say so in the test comment: the gate
  must not silently claim coverage it does not have.

### T006 — Docs and changelog

- `docs/development/how-to/pr-landing.md`, the `--prune` bullet in "Remove the
  worktree and branch": add one clause saying the branch is deleted only while
  it still points at the tip the prune proved (compare-and-swap), so a branch
  that moves in the meantime is kept and reported `BRANCH_MOVED`. Do not rewrite
  the section.
- `docs/changelog/unreleased/7212.fixed.md` — follow
  `docs/changelog/unreleased/README.md`; use `7212-<branch-slug>` as the id until
  the PR number exists, then rename the file to `<pr>.fixed.md`. One bullet,
  user-facing, with **Before:**/**After:**.

## Test strategy

Red-first, real git, no mocked subprocess for the defect reproduction:

```bash
uv run pytest tests/specify_cli/workspace/test_landed_worktrees.py -q
uv run pytest tests/specify_cli/git/test_destructive_guard_landed.py tests/git/test_delete_branch_ref.py -q
uv run pytest tests/architectural/test_destructive_op_routing.py -q
uv run pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -q
uv run ruff check <changed files> && uv run ruff format --check <changed files>
uv run mypy src/specify_cli/git/destructive_guard.py src/specify_cli/workspace/landed_worktrees.py
```

## Definition of Done

- T001 fails on the pre-fix tree for the right reason and passes after T002+T004.
- Every guard refusal in the landed path is a `DestructiveOpRefused`; no raw
  `GitCommandError`/`RefDelete*Error` reaches the prune for a race.
- `PruneOutcome` fields, JSON keys, recreate text and the refusal vocabulary for
  operators are unchanged; a moved branch reports `BRANCH_MOVED`.
- The routing gate is green, has no allowlist, and fails for a LANDED caller
  without `expected_tip` (proved by the planted test).
- Other intents/callers and `ref_advance.delete_branch_ref` are unchanged.
- Runbook clause and changelog fragment present; fragment renamed to the PR
  number once it exists.

## Risks

- Writing the keep-record before the CAS leaves a harmless create-only record if
  the CAS refuses; document it, do not add a cleanup delete of a bookkeeping ref.
- A `tip is None` path must not be turned into an unbound delete.
- Do not "simplify" by deleting the prune's fast path: it produces the refusal
  without touching refs and has its own test.

## Reviewer guidance

- Check the red test actually moves the ref *inside* the guarded call (after the
  prune's read), not before it — that is the window the issue names.
- Check the CAS old value is the assessed tip, not a re-read.
- Check no other delete caller or intent behaviour changed, and that the gate
  pin is non-vacuous.
