# Git Worktree and PR-Landing Workflow

Operational gotchas for working across multiple git worktrees of the same
repository and for landing a pull request. These are harness-neutral: they
follow from how git itself shares state across worktrees and how git hosts
authenticate pushes, not from any specific agent or tool.

## Shared stash stack across worktrees

- A repository's stash stack (`git stash list`) is a single ref shared by
  every worktree of that repository — it is not per-worktree. Running
  `git stash` in one worktree and `git stash pop` in another (or even in the
  same worktree at a later, unrelated point) can apply or drop a *different*
  worktree's work-in-progress.
- Do not use `git stash` / `git stash pop` as a general-purpose "get my
  changes out of the way" tool inside a worktree that is one of several
  active worktrees of the same repository. Prefer a worktree-local commit
  (even a throwaway "wip" commit that gets amended or reset later), or
  `git worktree` isolation itself, over the shared stash stack.
- If a stash absolutely must be used, pop it in the same command sequence
  that pushed it, without other git operations running concurrently in a
  sibling worktree.

Examples:

```bash
# Avoid: shared stash stack races with sibling worktrees
git stash
git stash pop

# Prefer: a worktree-local commit that doesn't touch shared state
git add -- <files you changed>
git commit -m "wip: checkpoint before rebase"
```

Stage only named files: a blanket add sweeps unrelated work and secrets into the checkpoint (Directive 033).

## Don't move a worktree's HEAD while a background job reads it

- If a test run, gate, or long build was started in the background against a
  worktree's working tree, do not `git checkout`, `git rebase`, `git reset`,
  or otherwise move that worktree's `HEAD` while the background job is still
  running. The job's already-open file handles and in-flight imports read
  from the paths as they existed at start time; moving `HEAD` underneath it
  shifts the source it is reading mid-run and produces results that do not
  correspond to any real commit.
- Wait for the background job to finish (or stop it deliberately) before
  changing what commit the worktree has checked out.

Examples:

```bash
# Avoid: rebasing a worktree while a background test run still reads it
git rebase origin/main &   # WRONG if a bg test is using this worktree right now

# Prefer: wait for the background job, then move HEAD
wait  # or: poll/monitor until the background run reports done
git rebase origin/main
```

## `--force-with-lease` rejection means origin moved, not "force harder"

- `git push --force-with-lease` fails with a message mentioning
  `(stale info)` when the remote-tracking ref it compared against is out of
  date — i.e., someone else pushed to that branch since you last fetched.
  This is the safety check working as intended, not a spurious failure.
- The correct recovery is `git fetch`, then reconcile the new remote commits
  (cherry-pick whichever ones are not already in your rebuilt history) before
  pushing again with a fresh lease. Do not fall back to plain `--force` —
  that silently discards the commits that arrived on the remote.

Examples:

```bash
git push --force-with-lease origin my-branch
# ! [rejected] my-branch -> my-branch (stale info)

git fetch origin
git log origin/my-branch --oneline   # see what landed since your last fetch
git cherry-pick <sha-of-unseen-commit>
git push --force-with-lease origin my-branch
```

## Fork pull-request pushes go over SSH, not HTTPS

- Pushing to a branch on a pull request opened from a fork can fail the
  git host's workflow-scope check when the remote is configured over HTTPS,
  even though read access and PR creation worked fine over HTTPS.
- Use (or add) an SSH remote for the fork and push over SSH instead of
  HTTPS when landing or rebasing commits onto a fork PR branch.

Examples:

```bash
git remote add fork-ssh git@github.com:<owner>/<repo>.git
git push fork-ssh HEAD:my-pr-branch
```

## Avoid

- `git stash` / `git stash pop` as a general scratch space inside a
  multi-worktree repository
- `git checkout`, `git rebase`, or `git reset` on a worktree while a
  background job is still reading that worktree
- plain `git push --force` as the response to a `--force-with-lease`
  `(stale info)` rejection
- pushing to a fork PR branch over HTTPS when the workflow-scope check
  rejects it — use SSH instead
