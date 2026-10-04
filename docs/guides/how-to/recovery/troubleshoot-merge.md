---
title: How to Troubleshoot Merge Issues
description: 'How to troubleshoot spec-kitty consolidate with Spec Kitty 3.2: resume or abort a stopped run and fix the refusals operators meet most, each with its command.'
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/missions/accept-and-merge.md
- docs/guides/how-to/missions/handle-dependencies.md
- docs/guides/how-to/missions/merge-mission.md
---
# How to Troubleshoot Merge Issues

Use this guide when `spec-kitty consolidate` stopped, refused to start, or was interrupted.

`consolidate` lands a Mission's lane branches on its mission branch, then lands the mission branch on the **local** target branch. It never publishes to origin unless you pass `--push`.

Each section gives what you see, what it means, and the command to run. The full list of exit codes and refusal codes is in the [CLI reference](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes); this guide covers the cases you are likely to meet.

## Quick Reference

| What happened | Run |
| --- | --- |
| The run was interrupted (terminal closed, process killed, a lane failed to merge) | `spec-kitty consolidate --resume` |
| You want to undo what the run moved and start over | `spec-kitty consolidate --abort` |
| You want to check readiness without changing anything | `spec-kitty consolidate --dry-run` |
| Exit code 75, `COORD_MOVED_AFTER_LANDING` | `spec-kitty consolidate --resume`, see [Exit code 75](#exit-code-75-the-landing-stands) |

## Resume an Interrupted Consolidation

Run the command from the repository root checkout:

```bash
spec-kitty consolidate --resume
```

Add `--mission <slug>` to name the Mission. Resume reads the record in `.kittify/runtime/merge/<mission_id>/state.json` and continues from the progress it holds.

Running `spec-kitty consolidate --mission <slug>` on a Mission with an unfinished record has the same effect: it prints `Detected interrupted merge` and resumes.

- **Strategy.** A resume keeps the strategy of the interrupted run. Passing a different `--strategy` is refused. Resume without `--strategy`, or run `--abort` and start again.
- **No record.** `No interrupted merge to resume.` means there is nothing to continue. Start a fresh run with `spec-kitty consolidate --mission <slug>`.
- **Worktree that shows staged deletions.** Do not commit them. See [Recover from an Interrupted Consolidation](recover-from-interrupted-merge.md#a-worktree-that-shows-staged-deletions-after-an-interruption).

## Undo a Run with --abort

```bash
spec-kitty consolidate --abort
```

`--abort` restores the branches the run moved (the target branch, the mission branch and the coordination branch) to the commits they had before the run. It restores a branch only while that branch is still at the commit this run recorded, so it never overwrites a commit that someone else added.

The command prints a rollback report with one line per branch. A branch is either restored, already at its snapshot, or marked `NOT restored` with the reason.

- **Everything restored.** The command exits 0 and clears the record.
- **A branch could not be restored.** The command exits 1 and keeps the record. Resolve the branch named in the report, then run `spec-kitty consolidate --abort` again.
- **The landing was already verified.** The command prints `Kept the landing verified by an earlier reconciliation`, rolls nothing back, exits 1 and keeps the record. Finish with `spec-kitty consolidate --resume` instead.

Lane branches are never moved. For a Mission with a coordination topology, `--abort` also removes the coordination worktree unless the Mission's `meta.json` retains worktrees.

For the full description, see [Recover from an Interrupted Consolidation](recover-from-interrupted-merge.md#aborting-a-consolidation).

## The Run Refused Before Moving Anything

These refusals stop the run before any branch moves. Fix the cause, then run `spec-kitty consolidate` again.

### Wrong branch or uncommitted changes

```text
Refusing destructive operation (MERGE_UNSAFE_PRIMARY_OFF_TARGET).
```

The repository root checkout is not on the branch `consolidate` expects. The refusal names the branch. Check it out in the repository root checkout:

```bash
git checkout <target-branch>
```

```text
Refusing destructive operation (MERGE_UNSAFE_PRIMARY_DIRTY).
Refusing destructive operation (MERGE_UNSAFE_WORKTREE_DIRTY).
```

The first code names the repository root checkout. The second names a lane worktree or the coordination worktree. The refusal lists the worktree and its dirty entries. Commit, stash or revert the changes in that worktree, then resume.

A lane worktree is checked only when the run is going to remove it. With `--keep-worktree`, a dirty lane worktree does not stop the run.

### Target-Branch Content Conflicts During Squash

```text
Default squash integration would conflict with newer target-branch content.
  diagnostic_code: TARGET_BRANCH_CONTENT_CONFLICT
  mission_branch: <mission-branch>
  target_branch: <target-branch>
  conflicting_path: <path>
```

The mission branch and a newer target-branch commit changed the same content. Spec Kitty does not pick a side. `--dry-run` reports the same code before anything moves, and it checks the mission branch as it stands now.

The remedy is to update the mission branch against the current target branch, resolve the listed paths, then rerun. Do the update in a separate worktree. `consolidate` refuses to run when the repository root checkout is off the target branch, so a checkout of the mission branch there would block the rerun.

```bash
git worktree add <path> <mission-branch>
git -C <path> merge <target-branch>
# Resolve each conflicting_path, stage it, then commit.
git -C <path> add src/path/to/file.py
git -C <path> commit
git worktree remove <path>
spec-kitty consolidate --dry-run
spec-kitty consolidate
```

### Not synchronized with origin (only with --push)

```text
diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
```

This check runs only when `--push` is in effect. A plain `consolidate` does not need the target branch to match origin. The code means the local target branch is ahead of, behind or diverged from its tracking branch.

Do not push the local target branch to satisfy the check; its extra commits may belong to other Missions. Choose one:

- **Run without `--push`.** Land locally, then publish through a topic branch and a pull request.
- **Use the focused pull request path the refusal prints.** It creates a branch from the mission branch, pushes that branch, and opens the pull request into the target branch.

## The Run Stopped After Moving Branches

### A lane failed to merge

```text
✗ <lane>: <error>
```

A lane could not be merged into the mission branch. The run exits 1 and rolls back the branches it moved. Fix the lane branch, then run `spec-kitty consolidate --resume`. If `--resume` answers `No interrupted merge to resume.`, the run left no record; run `spec-kitty consolidate --mission <slug>` instead. To drop the run, use `--abort`.

### Reconciliation FAILED or refused

```text
Reconciliation FAILED: <divergence>
Reconciliation refused (fail-closed): <reason>
```

After landing, `consolidate` checks that the target holds exactly the approved work. When the check fails or cannot decide, the run restores the branches it moved and prints the rollback report that starts `Rollback to the pre-consolidation snapshot:`.

Read the divergence or reason. It names the WP, the lane and the paths. Correct the lane, then run `spec-kitty consolidate` or `--resume`.

- **A FAIL cannot be overridden.** Correct the content on the lane through a surviving WP.
- **Missing or contradictory attribution about a canceled WP** can be attested after you check by hand that the canceled content is absent or superseded:

  ```bash
  spec-kitty consolidate --attest-canceled-superseded WP03 --attest-reason "<what you checked>"
  ```

  The flag is repeatable, one WP per use, and `--attest-reason` is required. It never lifts a FAIL. A `--dry-run` does not apply it.

The codes are defined in the [CLI reference](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes). The attribution rules and the full verdict table are in the [status model](../../../architecture/status-model.md#commit-attribution-stamp-policy_metadatalane_head).

### Exit code 75: the landing stands

Exit code 75 with `Error code: COORD_MOVED_AFTER_LANDING.` means the landing is verified, but a commit reached the coordination branch (or the mission branch) before it could be deleted. The branch is kept and nothing is rolled back. For a coordination branch, review the late commits with the `git log` command in the message, then run `spec-kitty consolidate --resume`.

See [Exit code 75](recover-from-interrupted-merge.md#exit-code-75-the-landing-stands-the-cleanup-did-not-finish) for the mission-branch variant.

## See Also

- [How to Merge a Mission](../missions/merge-mission.md): the normal consolidation flow
- [Accept and Merge](../missions/accept-and-merge.md): validation before consolidation
- [Handle Dependencies](../missions/handle-dependencies.md): WP dependency management
- [CLI reference: exit codes and refusal codes](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes)
- [Git workflow](../../../architecture/git-workflow.md#4-consolidated): what each consolidation step does
