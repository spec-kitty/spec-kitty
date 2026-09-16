---
title: Recover from an Implementation Crash
description: 'How to recover from an implementation crash with Spec Kitty 3.2: Learn how to restore a work package that is stuck in inprogress after an agent crash or.'
doc_status: active
updated: '2026-06-14'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/recovery/recover-from-interrupted-merge.md
---
# Recover from an Implementation Crash

Learn how to restore a work package that is stuck in `in_progress` after an agent crash or process kill.

## Detecting a Crash

A WP is stuck if:

- Its lane is `in_progress` in `status.events.jsonl` but no agent is running
- The worktree for the WP exists on disk but has no active process
- `spec-kitty doctor` reports a stale claim

Run the health check:

```bash
spec-kitty doctor
# or restrict to a specific mission:
spec-kitty doctor --mission 034-my-feature
```

The output flags:
- **Stale claims** — WPs in `claimed` for >7 days or `in_progress` for >14 days with no recent commits
- **Orphaned worktrees** — worktrees that exist but all their WPs are in terminal lanes
- **Zombie locks** — lock files left by a killed process

## Restore Execution Context with `--recover`

The fastest path back to a working state is:

```bash
spec-kitty implement WP02 --recover
```

This command:
1. Verifies the worktree exists and is on the correct branch
2. Re-emits a `claimed` → `in_progress` transition (without creating a new worktree)
3. Prints the workspace path so the agent can resume work

The `--recover` flag does not reset any code changes already committed in the worktree; it only repairs the status bookkeeping.

## Full Recovery Steps

If `--recover` alone is not enough (e.g., the worktree is corrupt or the branch is missing):

### Option A: Force WP back to `planned` and restart

```bash
# Reset status to planned with required feedback
printf '%s\n' "Recovery after crash; redispatch required." > /tmp/wp02-crash-feedback.md
spec-kitty agent tasks move-task WP02 --to planned \
  --review-feedback-file /tmp/wp02-crash-feedback.md

# Delete the broken worktree manually if needed
git worktree remove .worktrees/034-my-feature-lane-a --force

# Re-run implement to get a fresh workspace
spec-kitty implement WP02
```

### Option B: Continue in the existing worktree

```bash
# Confirm the worktree branch is clean enough to continue
cd .worktrees/034-my-feature-lane-a
git status

# Emit in_progress again to un-stale the claim
spec-kitty agent status emit WP02 --to in_progress --actor claude \
  --force --reason "Resuming after crash"
```

## Using `spec-kitty doctor`

`spec-kitty doctor` (added in 3.1.0) summarises the full health of all missions in one pass:

```
Stale claims
  WP02  034-my-feature  in_progress  last event: 15 days ago

Orphaned worktrees
  .worktrees/033-old-feature-lane-a  all WPs done

No zombie locks found.
```

Address each finding before restarting implementation to avoid double-claiming a WP or writing to a dangling worktree.

## See Also

- [Recover from Interrupted Merge](recover-from-interrupted-merge.md) — when `spec-kitty merge` was interrupted
- [CLI Reference: spec-kitty implement](../../../api/cli-commands.md#spec-kitty-implement)
- [CLI Reference: spec-kitty doctor](../../../api/cli-commands.md#spec-kitty-doctor)
- [Status Model](https://github.com/spec-kitty/spec-kitty/blob/main/docs/status-model.md) — how lane transitions are recorded
