# Research: Coordination Doctor Branch Safety

## Question

How can `spec-kitty doctor coordination --fix` repair a coordination branch that is
strictly behind its target without ever advancing an unrelated branch checked out in
the recorded coordination worktree?

## Evidence

1. GitHub issue #4920 supplies a current real-world reproduction: the coordination
   worktree path exists, but it has a different branch checked out. The command exits
   successfully, advances that different branch to the target tip, leaves the declared
   coordination branch stale, and prints a false `Fast-forwarded` message.
2. `src/specify_cli/cli/commands/_coordination_doctor.py` already owns the canonical
   read-only branch identity check in `_coord_worktree_head_finding`. It resolves the
   worktree's symbolic `HEAD` and emits
   `COORDINATION_WORKTREE_BRANCH_MISMATCH` when it differs from the declared
   coordination branch.
3. `_fix_one_mission_coord_staleness` validates ref ancestry, worktree existence, and
   worktree cleanliness, but does not validate symbolic `HEAD` before running
   `git -C <worktree> merge --ff-only <target_branch>`. Git therefore advances the
   branch actually checked out in that worktree.
4. The existing real-git contract in
   `tests/coordination/test_coord_staleness.py` proves correct-branch fast-forward,
   diverged-ref refusal, dirty-worktree refusal, and cross-mission continuation. It is
   the narrowest acceptance surface for the missing wrong-branch case.

## Decisions

### D1: Reuse the existing branch-identity authority

Call `_coord_worktree_head_finding(worktree, coord_branch)` inside the mutating repair
path before the cleanliness check or merge. Do not introduce a second symbolic-HEAD
resolver or infer identity from path names.

### D2: Fail closed as a structured blocked-fix error

When the worktree is on the wrong branch or detached, return the existing structured
`COORDINATION_BRANCH_STALE_FIX_BLOCKED` error shape. The finding must state the branch
mismatch, preserve the no-mutation contract, allow other missions' independent fixes to
continue, and cause the overall command to exit 1.

### D3: Verify the declared coordination ref after mutation

Only print `Fast-forwarded` after re-reading `refs/heads/<coordination_branch>` and
confirming that it equals the target SHA. This makes the success message evidence of the
declared ref's postcondition rather than an assumption based on pre-mutation SHAs.

### D4: Keep the change local and minimized

The smallest viable file set is the coordination doctor and its existing real-git
contract test. No workspace repair, branch checkout, forced reset, or general drift
reconciliation belongs in this fix.

## Test Strategy

- Add a real-git acceptance test where the declared coordination branch is stale, the
  recorded worktree has a different branch checked out, and that other branch is also a
  strict ancestor of the target.
- Prove before/after SHA identity for all three refs: declared coordination, wrong
  checked-out branch, and target.
- Require exit 1, a branch-mismatch blocked-fix finding, and absence of
  `Fast-forwarded` output.
- Retain the existing correct-branch control test unchanged and run the full
  `tests/coordination/test_coord_staleness.py` surface.

## Risks and Open Questions

- A branch can change between the precondition check and `git merge`; the local CLI is
  not a transaction coordinator for concurrent manual Git operations. The postcondition
  check prevents a false success in that race, while Git's own worktree rules and the
  fail-closed error preserve operator visibility.
- The broader possibility that the recorded path is not the expected registered
  worktree is outside #4920; this mission guards the concrete symbolic-HEAD invariant.
