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

This reads `.kittify/runtime/merge/<mission_id>/state.json`, skips already-completed WPs, and continues from the current WP. A resume reads the strategy and the target branch recorded in that file, so you do not repeat `--strategy` or `--target`. A `--strategy` that contradicts the recorded one is refused, and an explicit `--target` takes precedence over the recorded target.

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

To undo what an interrupted run moved and discard its record:

```bash
spec-kitty consolidate --abort
```

`--abort` first restores the branches the run moved: the target branch, the mission branch and the coordination branch. Each branch goes back to the commit it had before the run, and only while it is still at the commit this run recorded. A commit that someone else added since then is never overwritten. It clears the record only after every branch is restored.

The command prints a rollback report that starts `Rollback to the pre-consolidation snapshot:`, with one line per branch:

- **`restored`** shows the commit the branch left and the commit it returned to.
- **`unchanged`** means the branch was already at its snapshot.
- **`NOT restored`** names the branch, the commit observed and the commit expected, and the reason. A branch moved by another actor, or one that moved without a recorded tip, is reported this way.

What happens next depends on the report:

- **Everything restored.** The command prints `Aborted consolidation for <mission>` and exits 0. It also aborts a git merge left in the Mission's own scratch workspace, removes that workspace, and releases the merge lock it took.
- **A branch is `NOT restored`.** The command prints `Kept the consolidation record` and exits 1. Nothing was cleared. Resolve the branches the report names, then run `spec-kitty consolidate --abort` again.
- **The landing was already verified.** The command prints `Kept the landing verified by an earlier reconciliation`, rolls nothing back, exits 1 and keeps the record. Finish the run with `spec-kitty consolidate --resume`.
- **The record has no snapshot** (written by an older release). The command prints a notice that no branch is restored, clears the record and exits 0.
- **Another Mission's consolidation holds the merge lock and is still active.** The command refuses, exits 1, and restores and clears nothing. Finish or abort that consolidation first.

Lane branches are never moved by a consolidation, so `--abort` never moves them. A lane branch that was deleted since the run began is reported with the `git branch` command that recreates it, and does not block the abort.

`--abort` does not touch a git merge in progress in your own checkout. For a Mission with a coordination topology, it also removes the coordination worktree unless the Mission's `meta.json` retains worktrees (`retain_worktrees`); it then prints a notice.

## The consolidation state file

`.kittify/runtime/merge/<mission_id>/state.json` is written atomically at each WP boundary. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `mission_slug` | `str` | Mission slug being consolidated (e.g., `017-my-mission`) |
| `target_branch` | `str` | Branch being consolidated into (e.g., `main`) |
| `wp_order` | `list[str]` | Ordered WP IDs for the full consolidation sequence |
| `completed_wps` | `list[str]` | WPs already successfully consolidated |
| `current_wp` | `str \| null` | WP in progress when interrupted (null if between WPs) |
| `has_pending_conflicts` | `bool` | True if git merge conflicts are unresolved |
| `strategy` | `str` | `merge`, `squash`, or `rebase` |
| `started_at` | `str` | ISO 8601 timestamp of consolidation start |
| `updated_at` | `str` | ISO 8601 timestamp of last state write |

The file also holds the snapshot of the branches taken before the run moved anything, which `--abort` restores from. Do not edit or delete it. Use `--resume` or `--abort`.

## Consolidation Strategy Selection

The strategy is set at the start of a consolidation run with `--strategy`. Values are lower-case; `--strategy SQUASH` is rejected.

| Strategy | Effect |
|----------|--------|
| `merge` | Creates a merge commit; preserves full lane history. |
| `squash` | Collapses all lane commits into one commit on the target branch. **Default.** |
| `rebase` | Replays commits linearly; may conflict with remote linear-history protection if the branch was already pushed. |

```bash
spec-kitty consolidate --strategy squash
spec-kitty consolidate --strategy rebase --target main
```

Once a consolidation run is started with a strategy, that strategy is stored in `state.json` and used automatically on `--resume`.

## Manual Git Fallback

If `spec-kitty consolidate --resume` keeps failing, do not finish the landing with `git merge`, and do not delete `state.json`.

- A landing made by hand skips the reconciliation gate and the done bookkeeping that `consolidate` records.
- `state.json` holds the snapshot of the branches before the run moved anything. Deleting it removes what `--abort` needs to restore them.

Do this instead:

```bash
# 1. Read the progress and the recorded branch tips (read-only).
cat .kittify/runtime/merge/<mission_id>/state.json

# 2. Undo the run and clear the record.
spec-kitty consolidate --abort
```

Fix the cause the refusal named, then run `spec-kitty consolidate` again. If `--abort` reports `NOT restored` for a branch, that branch holds a commit the run did not record. Inspect it, resolve it, and run `--abort` again.

## See Also

- [Merge Feature](../missions/merge-mission.md) — full merge workflow
- [Recover from Implementation Crash](recover-from-implementation-crash.md) — when a WP is stuck mid-implementation
- [CLI Reference: spec-kitty consolidate](../../../api/cli-commands.md#spec-kitty-consolidate)
