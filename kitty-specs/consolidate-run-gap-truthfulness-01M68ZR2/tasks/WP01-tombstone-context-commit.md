---
work_package_id: WP01
title: Commit the tombstoned workspace contexts
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-002
- SC-001
planning_base_branch: issue-6450-consolidate-run-gap-truthfulness
merge_target_branch: issue-6450-consolidate-run-gap-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6450-consolidate-run-gap-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6450-consolidate-run-gap-truthfulness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-run-gap-truthfulness-01M68ZR2
base_commit: 3f802bc1a04cbe1d4ea64217180072b3b75fce17
created_at: '2026-10-31T12:48:47.388987+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Core fix
history:
- at: '2026-10-31T12:46:28Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/phase_teardown.py
- tests/specify_cli/test_workspace_context_tombstone.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Commit the tombstoned workspace contexts

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Load the PM profile first: `spec-kitty agent profile show python-pedro`, then
`spec-kitty charter context --action implement`.

---

## Objectives & Success Criteria

Fix #6450 item (4): `spec-kitty consolidate` tombstones a lane's
`.kittify/workspaces/<slug>-<lane>.json` when it removes that lane's worktree, but the tombstone
happens in `_phase_cleanup_worktrees_and_branches`, which runs *after*
`_phase_commit_and_assert` — the run's only bookkeeping commit
(`src/specify_cli/consolidation/executor.py:600-636`). In a project that tracks those JSON contexts,
the unlink is a real content change and the target branch is left dirty by a run that reported
success.

Done when:

- The new test in `tests/specify_cli/test_workspace_context_tombstone.py` fails on the unfixed code
  (working tree still dirty after cleanup) and passes after the fix.
- After the cleanup phase: both contexts are gone from disk, exactly **one** commit exists on the
  target, and that commit's path list contains only the context that was tracked before the run.
- `git status --porcelain` is empty afterwards, and no commit is created when no tracked context was
  removed (untracked/absent contexts, `--keep-worktree`, planning-artifact lanes).

## Context & Constraints

Read first:

- `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md` — FR-001, FR-002, SC-001, NFR-001,
  NFR-002, and the edge cases.
- `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/research.md` — D-02 (why the phase order is
  the defect) and the evidence list.
- `src/specify_cli/consolidation/phase_teardown.py` — `_remove_lane_worktrees` (the tombstone loop at
  the end) and `_phase_cleanup_worktrees_and_branches` (call site, `run.remove_worktree` gate).
- `src/specify_cli/consolidation/executor.py` — the phase order that puts the commit before cleanup.
- `src/specify_cli/git/bookkeeping_commit.py` — `commit_merge_bookkeeping`, the one sanctioned
  protected-flow commit seam; note `destination_ref_override` and the `paths` contract.
- `src/specify_cli/consolidation/phase_bookkeeping.py` — `_fold_alias_directory` and its
  "append the deletions AFTER the existence filter, on purpose" comment: the same deletion-staging
  contract this WP needs.
- `tests/specify_cli/test_workspace_context_tombstone.py` — the existing merge-completion tombstone
  tests and the `_run_cleanup_phase` harness this WP extends.

Constraints that matter:

- **NFR-001**: land the commit through `commit_merge_bookkeeping`; no new guarded call site, no raw
  `git commit`.
- **NFR-002**: at most one commit, and none when nothing tracked was removed.
- **C-002**: do not change the tombstone condition, the worktree-removal order, or any gate.
- Keep the existing three tombstone tests passing unchanged.

## Branch Strategy

- **Strategy**: workspace-per-work-package on a lanes-topology Mission; the WP executes in its
  computed lane worktree and merges back into the mission target branch.
- **Planning base branch**: `issue-6450-consolidate-run-gap-truthfulness`
- **Merge target branch**: `issue-6450-consolidate-run-gap-truthfulness`

> Populated by `specify_cli`. Do not edit by hand.

## Subtasks & Detailed Guidance

### T001 — Red-first test

Extend `tests/specify_cli/test_workspace_context_tombstone.py` with a real-git variant of the
existing merge-hook fixture:

1. `git init` a temp repo, commit a `.kittify/workspaces/m-lane-a.json` (tracked) and a
   `.kittify/workspaces/m-lane-b.json` (left untracked; add `.kittify/workspaces/m-lane-b.json` to
   `.git/info/exclude` if needed so `git status` does not report it as untracked).
2. Run `_run_cleanup_phase(run)` with `lane_ids=["lane-a", "lane-b"]`.
3. Assert both files are gone from disk, `git status --porcelain` is empty, and
   `git log --name-only -1` lists `m-lane-a.json` only.

Also add:

- a no-op case: a repo with only an **untracked** context → no new commit (`git rev-parse HEAD`
  unchanged) and the phase still succeeds;
- keep the existing three tests green.

Record the failing output before touching production code (the PR quotes it).

### T002 — Collect the unlinked, tracked contexts

In `_remove_lane_worktrees`, build the tombstone path set from the contexts the loop actually
unlinked (`context_path.exists()` before `delete_context`) and keep only those that were tracked in
the pre-run commit (`git ls-files --error-unmatch <path>` or an equivalent probe already used in the
consolidation package — do not shell out to a new ad-hoc command if a helper exists).

### T003 — Commit through the bookkeeping seam

After the tombstone loop, when the filtered set is non-empty, call `commit_merge_bookkeeping` with:

- `repo_root=run.main_repo`, `worktree_root=run.main_repo`
- `mission_slug=run.mission_slug`
- `branch=run.lanes_manifest.target_branch`, `destination_ref_override=run.lanes_manifest.target_branch`
  (same pattern as `_phase_commit_and_assert`)
- `message=f"chore({run.mission_slug}): tombstone lane workspace contexts"`
- `paths=tuple(filtered)`

Wrap the call so a failure warns (logger + console line naming the paths) and does **not** fail an
already-landed merge, matching the "keep the branch with a warning" tolerance of the neighbouring
lane-branch delete.

### T004 — Assertions, lint, typing

- Confirm the new assertions from T001 exercise both the commit and the no-op path.
- `uv run pytest tests/specify_cli/test_workspace_context_tombstone.py -q`
- `uv run pytest tests/consolidation -q` (regression net for the cleanup phase)
- `uv run ruff check src/specify_cli/consolidation/phase_teardown.py tests/specify_cli/test_workspace_context_tombstone.py`
- `uv run ruff format --check` on the same files, and `uv run mypy src/specify_cli/consolidation/phase_teardown.py`

## Test Strategy

Red-first, real git. The test drives the pre-existing cleanup phase on a real repository; the
assertion is the observable end state (clean working tree, one scoped commit), never a mock call
count.

## Definition of Done

- Red proof recorded, then green.
- Targeted suites, ruff and mypy clean on the touched paths.
- No change to the tombstone condition or to any gate decision.

## Risks

- `safe_commit` refuses a path that is neither on disk nor tracked → filter to tracked-and-unlinked
  paths only.
- A protected target refusal on the new commit must not fail the landed merge → warn, keep going,
  and say so in the trace/PR.

## Reviewer Guidance

Check that the commit's path list cannot include anything the loop did not unlink, that the
`--keep-worktree` and planning-lane cases still create no commit, and that the failure arm cannot
turn a landed merge into a failed run.
