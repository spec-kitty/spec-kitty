# Quickstart: reproduce the dropped commit and verify the fix

The pruner lives on the unmerged PR #7196 (`main` has no
`doctor workspaces --prune` yet), so run this on a branch stacked on that head.

## Reproduce (red)

```bash
git init -q -b main repo && cd repo
git config user.email t@example.invalid && git config user.name T
git commit -q --allow-empty -m base
git worktree add -q -b w2 .worktrees/w2 main
cd .worktrees/w2
git commit -q --allow-empty -m y                 # the branch's own work
git checkout -q --detach
git commit -q --allow-empty -m orphan-only       # reachable only from this reflog
git switch -q w2
cd ../..
git merge -q --ff-only w2                        # land it (no remote needed here)
```

Prune the worktree with the CLI, then collect garbage with reflogs expired:

```bash
spec-kitty doctor workspaces --prune
git -c gc.reflogExpire=now -c gc.reflogExpireUnreachable=now gc --prune=now
git cat-file -e "$(git rev-parse w2@{1})"        # before the fix: the object is gone
```

## Verify the fix

```bash
spec-kitty doctor workspaces --prune --json | jq '.pruned[0].kept_commits'
# ["refs/spec-kitty/discarded/reflog/<sha>", ...]
git cat-file -e <sha>                            # survives the gc above
git branch rescued refs/spec-kitty/discarded/reflog/<sha>
```

The text report prints the same ref on a `reflog-only commit kept at` line. A
rebase landing keeps nothing extra, and a merge commit is always kept when it
is the commit at risk.

## Tests

```bash
uv run --frozen pytest \
  tests/specify_cli/workspace/test_landed_worktrees.py \
  tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -q
```
