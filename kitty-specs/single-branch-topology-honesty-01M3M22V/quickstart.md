# Quickstart: single_branch and lane-tip guard

## Run a mission without lanes (explicit single_branch)

```bash
spec-kitty agent mission create my-fix --topology single_branch --json   # unprotected target: no branch minted
# protected target: kitty/mission-my-fix-<mid8> is created and checked out here
# opt out:           add --commit-to-target
spec-kitty agent mission finalize-tasks --mission my-fix                  # lanes.json: one repo-root lane
spec-kitty implement WP01                                                  # runs in this checkout, execution_mode direct_repo
spec-kitty agent tasks move-task WP01 --to for_review                      # no --force needed
spec-kitty implement WP02                                                  # refused while WP01 is in_progress
```

## Upgrade an existing project

```bash
spec-kitty upgrade               # re-stamps single_branch missions with code lanes to lanes
spec-kitty doctor topology       # reports SINGLE_BRANCH_CODE_LANES_UNMIGRATED if any remain
```

## Recover a destroyed lane

```bash
spec-kitty implement WP03        # DESTROYED_LANE: tip 1a2b3c... not on target
git branch kitty/mission-x-lane-b refs/spec-kitty/lane-tip/kitty/mission-x-lane-b   # restore
# or deliberately abandon:
git update-ref -d refs/spec-kitty/lane-tip/kitty/mission-x-lane-b
```
