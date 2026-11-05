# Quickstart — reproduce and verify the landed-delete race

**Mission**: `cas-landed-branch-delete-01M6P3ER` (issue #7212)
**Base**: this Mission is stacked on `issue-7173-landed-worktree-cleanup` (#7196).

## Environment

```bash
cd /home/exedev/work/sk-7212
git switch issue-7212-cas-landed-branch-delete
uv sync --frozen --all-extras
```

## Reproduce the defect (red, before the fix)

```bash
uv run pytest \
  tests/specify_cli/workspace/test_landed_worktrees.py::test_a_branch_moved_inside_the_delete_is_kept \
  -q
```

Observed before the fix: the branch `land-x` is gone after `prune_landed`, even
though it was moved to a fresh commit in the window between the prune's tip read
and the guard's delete; the outcome claims `branch_deleted`.

## Verify the fix

```bash
# The new behaviour, both directions (moved is kept, unmoved is deleted)
uv run pytest tests/specify_cli/workspace/test_landed_worktrees.py -q
# The guard's own contract
uv run pytest tests/specify_cli/git -q -k "branch_delete or destructive_guard"
# The structural pin (routing gate) and the shared CAS primitive
uv run pytest tests/architectural/test_destructive_op_routing.py tests/git/test_delete_branch_ref.py -q
# The CLI surface that prints the outcomes
uv run pytest tests/specify_cli/cli/commands/test_doctor_workspaces_prune.py -q
```

## Manual check (real repository)

```bash
git branch land-demo origin/main
git worktree add .worktrees/land-demo land-demo
# land it (merge or rebase-merge the branch into origin/main), then:
spec-kitty doctor workspaces --prune --json
```

A branch moved to a new commit in the window is now reported with
`"refusal": "BRANCH_MOVED"` and `"branch_deleted": false`; the branch still
exists at its new tip. An unmoved branch is deleted and its recreate command is
printed.

## What must stay true

- `git for-each-ref refs/spec-kitty/discarded/` shows a keep-record for a pruned
  branch whose tip no local branch or tag reached (unchanged).
- `--force-recreate` and `mission close --discard` behave exactly as before.
- The destructive-op routing gate is green with no allowlist and no new
  destructive literal outside the guard-internal modules.
