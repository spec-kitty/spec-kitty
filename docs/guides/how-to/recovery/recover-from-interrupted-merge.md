---
title: Recover from an Interrupted Consolidation
description: 'How to recover from an interrupted consolidation with Spec Kitty 3.2: Learn how to resume or abort a spec-kitty consolidate run that was interrupted before it completed.'
doc_status: active
updated: '2026-10-04'
type: how-to
audience: docs/context/audience/external/project-owner.md
related:
- docs/guides/how-to/missions/merge-mission.md
- docs/guides/how-to/recovery/recover-from-implementation-crash.md
---
# Recover from an Interrupted Consolidation

Learn how to resume or abort a `spec-kitty consolidate` run that was interrupted before it completed.

## Why Consolidation Runs Can Be Interrupted

A `spec-kitty consolidate` operation touches multiple git refs in sequence (lane branches → mission branch → target branch). It can be interrupted by:

- **Network loss** during a `git push` after consolidation
- **Linear-history branch protection** rejecting a merge or rebase commit
- **Process kill** (Ctrl-C, timeout, OOM) mid-sequence
- **Merge conflict** that requires manual resolution

When an interruption occurs, spec-kitty saves progress to `.kittify/runtime/merge/<mission_id>/state.json` before exiting. This file records which WPs have already been consolidated and which remain, so the operation can be resumed without re-doing completed work.

## Resuming with `--resume`

Once the blocking condition is resolved (conflict fixed, push retried, etc.), run:

```bash
spec-kitty consolidate --resume
```

This reads `.kittify/runtime/merge/<mission_id>/state.json`, skips already-completed WPs, and continues from the current WP. The `--strategy` and `--target` values from the original invocation are preserved in the state file and do not need to be repeated.

### A worktree that shows staged deletions after an interruption

A run that is interrupted after it advanced a branch, but before it refreshed the
worktree that has that branch checked out, leaves the worktree behind its own
HEAD. `git status` there shows the newly integrated files as staged deletions.
They are the integrated work read in reverse.

**Do not commit, stage or stash them.** Committing them reverts the work that was
just integrated; a later `consolidate` then fails with `APPROVED_CONTENT_MISSING`
and rolls back.

Run `spec-kitty consolidate --resume` instead. When the worktree only lags its
own HEAD, the resume refreshes it in place and continues. This applies to the
repository root checkout, the coordination worktree, a mission worktree and a
lane worktree.

The resume refuses, before it changes anything, in these cases:

- **The worktree lags and also holds an edit of your own** (coordination,
  mission or lane worktree). The refusal prints the exact commands, in this
  order: save your edit as a patch outside the worktree (`git diff --binary`),
  refresh the worktree (`git reset --hard HEAD`), run
  `spec-kitty consolidate --resume`, and only then re-apply the patch
  (`git apply`). Follow them as printed; `git stash` is ruled out by name
  because popping the stash after the refresh deletes the integrated files
  again.
- **A git `index.lock` is left behind.** The checkout state is unknown. Confirm
  that no other git process is running, remove the lock file named in the
  message, and resume.

### Exit code 75: the landing stands, the cleanup did not finish

`spec-kitty consolidate` exits with code 75 and a message ending in
`Error code: COORD_MOVED_AFTER_LANDING.` when the landing was verified and the
coordination branch (or the mission branch of a Mission without a coordination
topology) then received a commit before it could be deleted. The branch is kept,
the late commit is intact and the target is not rolled back.

- **Coordination branch:** review the late commit(s) with the `git log` command
  in the message, then run `spec-kitty consolidate --resume`. It lands the late
  commit(s) on the target and finishes the teardown.
- **Mission branch without a coordination topology:** land the commit(s) that
  belong on the target yourself, then delete the branch.

The other codes `consolidate` can report are listed in the
[CLI reference](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes).

## Aborting a Consolidation

To discard saved state and abort any in-progress git merge:

```bash
spec-kitty consolidate --abort
```

This runs `git merge --abort` (if a merge is in progress) and deletes `.kittify/runtime/merge/<mission_id>/state.json`. The worktrees and branches are left intact so you can restart from scratch.

## The consolidation state file

`.kittify/runtime/merge/<mission_id>/state.json` is written atomically at each WP boundary. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `feature_slug` | `str` | Mission slug being consolidated (e.g., `017-my-feature`) |
| `target_branch` | `str` | Branch being consolidated into (e.g., `main`) |
| `wp_order` | `list[str]` | Ordered WP IDs for the full consolidation sequence |
| `completed_wps` | `list[str]` | WPs already successfully consolidated |
| `current_wp` | `str \| null` | WP in progress when interrupted (null if between WPs) |
| `has_pending_conflicts` | `bool` | True if git merge conflicts are unresolved |
| `strategy` | `str` | `MERGE`, `SQUASH`, or `REBASE` |
| `started_at` | `str` | ISO 8601 timestamp of consolidation start |
| `updated_at` | `str` | ISO 8601 timestamp of last state write |

Do not edit this file manually. Use `--resume` or `--abort`.

## Consolidation Strategy Selection

The strategy is set at the start of a consolidation run with `--strategy`:

| Strategy | Effect |
|----------|--------|
| `MERGE` | Creates a merge commit; preserves full lane history. |
| `SQUASH` | Collapses all lane commits into one commit on the target branch. **Default.** |
| `REBASE` | Replays commits linearly; may conflict with remote linear-history protection if the branch was already pushed. |

```bash
spec-kitty consolidate --strategy SQUASH
spec-kitty consolidate --strategy REBASE --target main
```

Once a consolidation run is started with a strategy, that strategy is stored in `state.json` and used automatically on `--resume`.

## Manual Git Fallback

If `spec-kitty consolidate --resume` itself fails, you can complete the consolidation manually:

```bash
# 1. Check which lane branch needs merging (from .kittify/runtime/merge/<mission_id>/state.json)
cat .kittify/runtime/merge/<mission_id>/state.json

# 2. Merge the lane branch into the mission branch manually
git checkout kitty/mission-<feature>
git merge kitty/mission-<feature>-lane-a --no-edit

# 3. Merge the mission branch into target
git checkout main
git merge kitty/mission-<feature> --no-edit

# 4. Clean up consolidation state
rm .kittify/runtime/merge/<mission_id>/state.json
```

After a manual consolidation, run `spec-kitty upgrade` to ensure any post-consolidation hooks (worktree cleanup, status events) complete correctly.

## See Also

- [Merge Feature](../missions/merge-mission.md) — full merge workflow
- [Recover from Implementation Crash](recover-from-implementation-crash.md) — when a WP is stuck mid-implementation
- [CLI Reference: spec-kitty consolidate](../../../api/cli-commands.md#spec-kitty-consolidate)
