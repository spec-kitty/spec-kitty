# Phase 0 Research — compare-and-swap branch delete for the landed prune

**Mission**: `cas-landed-branch-delete-01M6P3ER` · **Issue**: #7212 · **Base**: `issue-7173-landed-worktree-cleanup` (open #7196)

## R1. The defect, reproduced by reading the two call layers

`prune_landed` → `_prune_one` → `_still_landed_refusal` (fresh assessment, same
tip) → `guarded_worktree_remove` → `_delete_landed_branch`:

```python
live = branch_tip(repo_root, branch)        # read #1 (the prune's "immediately before")
if live != tip: return ... BRANCH_MOVED
...
recorded = guarded_branch_delete(..., operator_intent=LANDED_INTENT)
```

`guarded_branch_delete(LANDED_INTENT)` → `_discard_branch_keeping_tip`:

```python
if _unique_commits(...):                    # decides whether a keep-record is needed
    tip = branch_tip(repo_root, branch)     # read #2, independent of read #1
    _keep_discarded_tip(...)                # record that moved tip
_git_ok(repo_root, ["branch", "-D", "--", branch])   # delete, bound to nothing
```

Between read #1 (the only value the prune proved absorbed) and `branch -D`, an
actor may move the ref. The delete then removes whatever the ref holds — the
commit past the assessed tip is gone, and when the assessed tip was already
reachable from another local branch or tag, no keep-record is written either
(`_unique_commits` returns empty for the *new* tip if that tip is reachable, and
for the *old* tip it may be non-unique). The window is small but real: the
prune runs in a shared clone where another agent or terminal may commit.

This is the exact shape #5570 fixed for the coordination branch, and
`b37f3f9085` (`fix(landing): delete the orchestrator-api mission branch by
compare-and-swap`) fixed for the orchestrator-api mission branch. Both went
through `ref_advance.delete_branch_ref`, documented as "one compare-and-swap
`git update-ref -d <ref> <expected_sha>` (3-arg), so a commit that landed after
the caller approved `expected_sha` is never made unreachable (#5570)".
`delete_branch_ref` also keeps the checked-out-branch protection that
`update-ref -d` bypasses (#3926).

## R2. Which side is wrong: the ordering is right, the binding is not

The prune's order is deliberate and documented in the #7173 record
(`kitty-specs/landed-worktree-cleanup-01M6KZNP/tasks/WP03-landed-assessment-and-prune.md`):
re-assess each landed candidate, remove the worktree, then delete the branch.
Reversing it is not an option — git refuses to delete a branch a worktree has
checked out — so the delete must stay after the removal. The data-loss window
is therefore not an ordering defect *in the prune*; it is a **binding** defect
in the delete primitive. A caller-side read can never be atomic with a later
subprocess; only the delete itself can carry the precondition. The prune's own
comparison stays as a cheap fast path (it produces `BRANCH_MOVED` without
touching refs, and it already has a test), but it is no longer the safety
argument.

## R3. Options considered

| Option | Verdict |
| --- | --- |
| **A. Reuse `ref_advance.delete_branch_ref` behind `guarded_branch_delete(..., expected_tip=...)`** | **Chosen.** One CAS implementation in the tree already (canonical-source-unification); keeps the guard as the typed chokepoint by mapping `RefDelete*Error` to `DestructiveOpRefused`; keeps the checked-out protection; the destructive-op census is untouched because both modules are guard-internal. |
| B. Add a raw `git update-ref -d <ref> <expected>` argv inside `destructive_guard.py` (the issue's literal proposal) | Rejected: a second CAS delete implementation, and it loses `delete_branch_ref`'s checked-out guard and mismatch diagnosis. The census would accept it (the guard is excluded), which is precisely why the duplication would go unnoticed. |
| C. Re-read the tip inside the guard and compare immediately before `branch -D` | Rejected: that is the same read-then-delete with one more read; the window just moves. The issue exists because read-then-delete cannot be closed from the caller side. |
| D. Reorder the prune (delete the branch before removing the worktree) | Rejected: git refuses; and it would trade a millisecond race for a broken invariant. |
| E. Make `LANDED_INTENT` always CAS without a new parameter (derive the tip inside the guard) | Rejected: the guard would then bind the delete to a tip it chose, not to the tip whose absorption the prune proved. The expected value must come from the proof. |

## R4. Guard API and refusal mapping

- New keyword-only parameter `expected_tip: str | None = None` on
  `guarded_branch_delete`.
- `operator_intent == LANDED_INTENT` without `expected_tip` raises
  `ValueError` before any git call: every landed delete must name the tip it
  approved. A future call site cannot reintroduce read-then-delete silently.
- With `expected_tip` set (LANDED; the other intents keep their current
  behaviour and never pass it):
  1. reject a branch that is not at `expected_tip` up front
     (`DestructiveOpRefused`, moved-tip code) — no keep-record, no delete;
  2. run the existing unique-commit scan and, if the tip has no other local
     branch or tag, write the create-only keep-record at **`expected_tip`**
     (crash safety: record before delete);
  3. delete through `ref_advance.delete_branch_ref(repo_root, branch,
     expected_tip)`.
- `RefDeleteMismatchError` → `DestructiveOpRefused(BRANCH_TIP_MOVED)`;
  `RefDeleteCheckedOutError` → `DestructiveOpRefused(BRANCH_CHECKED_OUT)`;
  `RefDeleteError` (and its worktree-enumeration sibling `RefAdvanceError`)
  → `DestructiveOpRefused(BRANCH_DELETE_REFUSED_BY_GIT)`. No untyped git
  error escapes for an expected race (C-003).

**Aggregate review finding (fixed before the PR).** `git update-ref -d`
dereferences a symbolic ref: a branch made a symref to `refs/heads/main`
would have made the CAS delete `main` (the probe for a checked-out branch
looks at the branch name, not at the symref target). `git branch -D`, the
path this replaces, deletes only the named ref. The primitive now deletes
with `update-ref --no-deref -d`, restoring the old semantics for every
caller, with a symref regression test at the primitive and at the guard.
- The prune maps `BRANCH_TIP_MOVED` → its existing `BRANCH_MOVED` and
  `BRANCH_CHECKED_OUT` → `BRANCH_IN_OTHER_WORKTREE`, so the operator-facing
  vocabulary and JSON shape do not change (FR-005).

## R5. Residuals and non-goals

- A refused CAS may leave the create-only `refs/spec-kitty/discarded/<branch>`
  record written in the same window. It is harmless, idempotent, and keeps the
  assessed tip reachable; the branch also still holds its tip. Documented in the
  guard docstring rather than "fixed" with a delete of the record (deleting a
  bookkeeping ref to tidy up is riskier than keeping it).
- `git branch -D` also removes `branch.<name>.*` config; `update-ref -d` does
  not. `delete_branch_ref` has shipped without that cleanup since #5570 and the
  orchestrator-api path relies on it; this Mission does not change that shared
  primitive (locality of change). The prune's recreate command sets the branch
  up explicitly from a SHA.
- No new fetch, no new process probe, no change to the absorption proof, the
  verdict order, the upgrade surface or the CLI contract. Cost: the bound
  delete adds at most two git invocations per pruned branch (the guard's tip
  re-read for a clean refusal, and the worktree scan `delete_branch_ref`
  keeps because `update-ref -d` bypasses git's checked-out protection);
  NFR-003 is stated as that bound, not as zero.

## R6. Evidence the change is testable without timing

The window is simulated by wrapping `landed_worktrees.guarded_branch_delete` in
the test: the wrapper advances the ref to a fresh `commit-tree` commit (reached
by no other ref) and then calls the real guard. That is deterministic, uses the
real production entry point (`prune_landed`), and fails on the pre-fix tree
every run. The positive control on the same fixture shape leaves the ref alone
and asserts the branch is deleted.
