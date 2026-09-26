# Coordination Repair Safety Contract

`spec-kitty doctor coordination --fix` may fast-forward a mission's declared
coordination branch only when the recorded coordination worktree has that exact branch
checked out and the ref is a clean strict ancestor of the target.

Before mutation, the command uses the canonical `_coord_worktree_head_finding` check.
A wrong branch, detached `HEAD`, dirty worktree, or diverged ref returns the existing
`COORDINATION_BRANCH_STALE_FIX_BLOCKED` finding and does not mutate refs. A blocked
mission does not abort fixes for unrelated missions.

After `git merge --ff-only`, the command re-reads `refs/heads/<coordination-branch>`.
It prints `Fast-forwarded` only when that ref equals the target SHA. A postcondition
failure returns the same stable blocked-fix code and emits no success message.

## Verification

- The wrong-branch real-Git regression snapshots and compares the declared branch,
  wrong checked-out branch, worktree `HEAD`, and target branch before and after.
- The correct-branch real-Git control proves the declared ref reaches the target.
- A focused postcondition test proves a merge subprocess return alone cannot produce
  a successful message.
- Validation on 2026-09-22: 30 focused tests and 183 coordination tests passed;
  targeted Ruff lint and strict MyPy passed.
- Known shared-baseline failures are tracked separately in #4873 and #4506.
