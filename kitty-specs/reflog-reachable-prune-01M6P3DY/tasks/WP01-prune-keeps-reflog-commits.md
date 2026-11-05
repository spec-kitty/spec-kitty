---
work_package_id: WP01
title: Prune keeps commits only a reflog still reached
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-007
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-7211-reflog-reachable-prune
merge_target_branch: issue-7211-reflog-reachable-prune
branch_strategy: Planning artifacts for this mission were generated on issue-7211-reflog-reachable-prune. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7211-reflog-reachable-prune unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/workspace/landed_worktrees.py
- src/specify_cli/git/destructive_guard.py
- src/specify_cli/cli/commands/_landed_worktree_doctor.py
- tests/specify_cli/workspace/test_landed_worktrees.py
- tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Prune keeps commits only a reflog still reached

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make `prune_landed` record every commit that only a worktree HEAD reflog or a branch reflog still reached, under `refs/spec-kitty/discarded/reflog/<sha>`, before it removes the worktree and deletes the branch — and refuse the removal when that record cannot be written. Prove it red-first through the CLI.

## Context

`src/specify_cli/workspace/landed_worktrees.py` (`_prune_one`) removes landed worktrees. Two records die with the prune: `git worktree remove` deletes `.git/worktrees/<id>/logs/HEAD`, and `git branch -D` deletes the branch reflog. A commit made while detached, or dropped by `git reset --hard`, is then reached by no ref and no reflog, and `git gc` may collect it. The landed proof today covers only the branch tip (`keep_detached_tip`, the guard's `LANDED_INTENT`).

The rule this WP implements (see `spec.md`):

> Before the prune destroys a reflog, every commit that reflog reached is reachable from a ref afterwards, or it is provably still on the primary ref by patch.

Read `plan.md` §Design for the mechanism. `PruneOutcome.to_json` is consumed by `doctor workspaces --json`; the new key must be additive (`NFR-003`).

This WP is stacked on the unmerged PR #7196 head; `main` does not have this module yet. Do not rebase onto `main` and do not modify anything outside `owned_files`.

## Subtask T001: Red-first CLI test for the detached-only commit

**Purpose**: Reproduce the issue through the production entry point and watch it fail.

**Steps**:

1. In `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py`, add a test (for example `test_prune_keeps_a_commit_only_the_worktree_head_reflog_reached`) that builds the issue's reproduction on a scratch repository, reusing the file's existing fixture helpers for a landed worktree.
2. The fixture must: create branch `w2` with a commit, `git checkout --detach`, commit `orphan-only`, `git switch w2`, land `w2` on the primary (the existing helpers already produce a landed branch), then run the CLI with `doctor workspaces --prune --json`.
3. Assertions, all after the prune:
   - the orphan commit is reachable from a ref: `git rev-list --all --contains <sha>` is non-empty and the ref is under `refs/spec-kitty/discarded/reflog/`;
   - it survives `git gc --prune=now -c gc.reflogExpire=now --prune=now` and `git cat-file -e <sha>` still succeeds (assert reachability from a ref, never from a reflog — `SC-005`);
   - the JSON payload names the kept ref in the prune outcome.
4. Run it and record the failure (the commit is unreachable today, so the test fails). Paste the failure line into the review-cycle evidence.

**Files**: `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py` (+~70 lines).

**Validation**: `uv run --frozen pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -k reflog --no-header -x` fails for the expected reason before the fix.

## Subtask T002: Red-first test for the branch-reflog commit dropped by a reset

**Purpose**: Cover the second reflog the issue names.

**Steps**:

1. In the same module, add a test (for example `test_prune_keeps_a_commit_only_the_branch_reflog_reached`): commit on the landed branch, `git reset --hard HEAD~1` so the dropped commit is reachable only from the branch reflog, then prune.
2. Assert the dropped commit is held by a `refs/spec-kitty/discarded/reflog/` ref and survives `git gc --prune=now` with reflogs expired.
3. Confirm it fails before the fix.

**Files**: `tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py` (+~50 lines).

**Validation**: same command as T001, twice red before the fix.

## Subtask T003: Reflog candidates and post-prune reachability

**Purpose**: The decision logic, in the workspace module.

**Steps**:

1. Add module-level helpers to `src/specify_cli/workspace/landed_worktrees.py` (private, near `_keep_detached`):
   - `_reflog_commits(repo_root, rev) -> list[str]` — `git reflog show --format=%H <rev>` with `check=False`; a non-zero exit (no reflog) yields `[]`, never an error.
   - `_reflog_candidates(repo_root, verdict) -> list[str]` — the union of `_reflog_commits(repo_root, "HEAD")` run inside `verdict.path` and `_reflog_commits(repo_root, f"refs/heads/{verdict.branch}")` when `verdict.branch` is not `None`, de-duplicated in reflog order.
   - `_surviving_ref_shas(repo_root, *, doomed_branch: str | None) -> list[str]` — `git for-each-ref --format=%(objectname) refs/`, dropping the entry whose refname is `refs/heads/<doomed_branch>` (print both fields and split, as `destructive_guard._unique_commits` does).
   - `_unreachable_after_prune(repo_root, candidates, surviving) -> list[str]` — `git rev-list <candidates>` with `^<sha>` lines for the surviving refs on stdin, following the guard's stdin form so a long argument list cannot overflow.
2. Keep the read-side honest: an unreadable reflog means "no candidates", never a prune failure.

**Files**: `src/specify_cli/workspace/landed_worktrees.py` (+~55 lines).

**Validation**: unit tests in `tests/specify_cli/workspace/test_landed_worktrees.py` for a no-reflog branch (`[]`), a detached HEAD reflog candidate, and a candidate that another ref still reaches (excluded).

## Subtask T004: `keep_reflog_tip` create-only ref write in the guard

**Purpose**: One canonical create-only write, beside the guard's other discarded refs.

**Steps**:

1. In `src/specify_cli/git/destructive_guard.py`, beside `keep_detached_tip`, add:
   - `RELOG_DISCARDED_REF_PREFIX = f"{DISCARDED_REF_PREFIX}reflog/"`;
   - `keep_reflog_tip(repo_root: Path, sha: str, *, env: dict[str, str] | None = None) -> str` — writes `refs/spec-kitty/discarded/reflog/<sha>` via `_keep_discarded_tip` (create-only, idempotent when the ref already holds `sha`) and raises `DestructiveOpRefused(DESTRUCTIVE_OP_ONLY_COPY)` with a remediation naming the sha and the prefix when it cannot write. Mirror `keep_detached_tip`'s docstring style and add the new name to the module's exports if that module keeps a list.
2. Do **not** widen the `LANDED_INTENT` caller allowlist: this is a bookkeeping write, not a delete.

**Files**: `src/specify_cli/git/destructive_guard.py` (+~25 lines).

**Validation**: `tests/specify_cli/git/test_destructive_guard_landed.py` gains a test that the ref is created, that a second call is a no-op, and that a failed write raises `DESTRUCTIVE_OP_ONLY_COPY`. (That file is outside `owned_files`; if ownership forbids editing it, put the guard test in `tests/specify_cli/workspace/test_landed_worktrees.py` instead, through `prune_landed`.)

## Subtask T005: Wire the keep step into `_prune_one` before anything is destroyed

**Purpose**: Ordering is the safety property.

**Steps**:

1. In `_prune_one`, after `_still_landed_refusal` and before `guarded_worktree_remove`:
   - keep the detached tip exactly as today (`_keep_detached`);
   - compute `candidates = _reflog_candidates(...)`, then `surviving = _surviving_ref_shas(repo_root, doomed_branch=verdict.branch)` (re-read after `_keep_detached` so the just-written ref counts as surviving), then `unreachable = _unreachable_after_prune(...)`;
   - filter with the patch check below and write each kept sha with `keep_reflog_tip`;
   - a `DestructiveOpRefused` from the write returns `_outcome(verdict, removed=False, refusal=exc.error_code)` — nothing removed (`FR-005`).
2. Patch narrowing helper `_patch_on_primary(repo_root, primary_ref, sha) -> bool`:
   - `git cherry <primary_ref> <sha>` (or the equivalent `rev-list --cherry-pick`); return `True` only when every printed line starts with `-`;
   - empty output (a merge commit) or a git error returns `False`, so the commit is kept (`FR-004` — the check may only skip a duplicate, never drop something unproven).
3. Add `kept_commits: tuple[str, ...] = ()` to `PruneOutcome` (default keeps every existing construction valid) and serialise it as `"kept_commits": list(...)` in `to_json` (`NFR-003`); thread the values through `_outcome`.

**Files**: `src/specify_cli/workspace/landed_worktrees.py` (+~50 lines).

**Validation**: T001/T002 turn green; SC-004's refusal test (force `keep_reflog_tip` to raise) leaves the worktree and branch in place with `DESTRUCTIVE_OP_ONLY_COPY`.

## Subtask T006: Render the kept refs

**Purpose**: An operator must be able to find and restore the work.

**Steps**:

1. In `src/specify_cli/cli/commands/_landed_worktree_doctor.py`, `_render_outcome`: print one line per kept ref, for example `reflog-only commit kept at refs/spec-kitty/discarded/reflog/<sha>`, after the existing `tip kept at ...` line. Use the module's `_print` and `escape` so paths stay copyable.
2. Keep `kept_ref` unchanged and do not reorder existing lines.
3. Extend the JSON test to assert the new key is additive: the pre-existing keys are still present with their meanings.

**Files**: `src/specify_cli/cli/commands/_landed_worktree_doctor.py` (+~8 lines), tests.

**Validation**: the T001 test asserts the text output names the ref as well as the JSON.

## Subtask T007: Non-churn, idempotence, and offline coverage

**Purpose**: The fix must cost the common landing nothing and must not need a remote.

**Steps**:

1. Add `test_prune_of_a_rebased_landing_branch_keeps_no_reflog_ref`: three commits on the branch, rebase-landed onto the primary (so the reflog holds pre-rebase shas), prune, then `git for-each-ref refs/spec-kitty/discarded/reflog` is empty and no candidate was kept (`FR-007`, `SC-003`).
2. Add `test_prune_is_idempotent_for_a_kept_reflog_commit`: run the prune twice (the second run finds no landed worktree) and the ref still holds the sha.
3. Add `test_prune_without_a_remote_records_reflog_commits`: the fixture has no remote configured; the prune still succeeds and keeps the orphan commit (`NFR-001`); assert the run made no network call by construction (no remote exists) rather than by mocking.
4. Add the `NFR-002` bound as a comment-backed assertion where practical (a candidate count of one keeps extra git invocations small); do not add a fragile process-level counter.

**Files**: `tests/specify_cli/workspace/test_landed_worktrees.py` (+~120 lines).

**Validation**: `uv run --frozen pytest tests/specify_cli/workspace/test_landed_worktrees.py tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -q` is green.

## Definition of Done

- The two red-first tests (T001, T002) fail before the change and pass after it; each is recorded with `spec-kitty agent tasks mark-status <T-id> --status done` once it does.
- A commit reachable only from a worktree HEAD reflog, and one reachable only from a branch reflog, are held by `refs/spec-kitty/discarded/reflog/<sha>` after the prune and survive `git gc --prune=now` with reflogs expired.
- A rebased landing branch adds no kept ref.
- A failed record refuses the removal, leaving worktree and branch in place, with the guard's `DESTRUCTIVE_OP_ONLY_COPY`.
- The text report and `--json` both name the kept refs; every pre-existing JSON key is unchanged.
- `ruff check` and the two suites above are clean; no gate, allowlist or existing assertion was weakened.

## Risks

- **Reflog entry vs. ancestor**: candidates are reflog entry shas; their ancestors are covered transitively. Do not use `rev-list <sha>` alone as the candidate set or a deep chain writes a ref per commit.
- **Stale primary**: `git cherry` reads the local primary ref. A stale ref can make a superseded commit look patch-equivalent; that is the same risk the absorption proof already documents, and the content is still on that ref. Never invert the check into "drop when unsure".
- **Windows**: `git worktree remove` on Windows may keep files briefly; the existing helpers already handle the removal, so do not add platform-specific paths.
- **Ordering regression**: any future reordering that writes the reflog refs after the removal re-opens the data-loss window; the module docstring must state the order.

## Reviewer Guidance

- Verify the write happens strictly before `guarded_worktree_remove` and before `_delete_landed_branch`.
- Verify no verdict, guard or gate is relaxed: `C-001` is the class of change to reject.
- Verify the patch check is fail-closed: empty output, merge commits and errors all keep.
- Verify the tests prove reachability from a ref (`for-each-ref --contains`, `git cat-file -e` after `gc --prune=now`), not from a reflog.
- Verify `PruneOutcome.to_json` is additive and `kept_ref` keeps its meaning.
