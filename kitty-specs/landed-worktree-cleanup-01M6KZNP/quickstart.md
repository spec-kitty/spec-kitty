# Quickstart

```bash
# See which worktrees have landed (writes nothing)
spec-kitty doctor workspaces

# Remove the landed ones and their local branches; prints a recreate command for each
spec-kitty doctor workspaces --prune

# Upgrade: Mission worktrees and non-selected worktrees are left alone
spec-kitty upgrade --dry-run
spec-kitty upgrade --include-worktree .worktrees/wip-x
spec-kitty upgrade --all-worktrees
```

Run `git fetch origin` first if you want worktrees merged since your last fetch to count as landed; the doctor never fetches.
