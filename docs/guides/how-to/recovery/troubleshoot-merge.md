---
title: How to Troubleshoot Merge Issues
description: 'How to troubleshoot spec-kitty consolidate with Spec Kitty 3.2: resume or abort a stopped run and fix the refusals operators meet most, each with its command.'
doc_status: active
updated: '2026-10-07'
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
| `UNEXPLAINED_BRANCH_MOVE` on a re-run or `--resume` | Inspect the branch, see [A branch moved without a record](#a-branch-moved-without-a-record) |
| `--abort` keeps reporting a branch `NOT restored` | `spec-kitty consolidate --abort --release-branch <branch> --release-reason "<why>"`, see [Keep a branch that cannot be restored](#keep-a-branch-that-cannot-be-restored) |
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

`--abort` restores the branches the run moved (the target branch, the mission branch and the coordination branch) to the commits they had before the run. It restores a branch only while that branch is still at the commit this run recorded, or at a commit the run saved as its next move before it was interrupted. It never overwrites a commit that someone else added, and it never treats a commit it cannot explain as already restored.

The command prints a rollback report with one line per branch. A branch is restored, already at its snapshot (`unchanged`), kept by an operator release (`kept`), or marked `NOT restored` with the reason. A restore marked `adopted interrupted advance` undid a move the interrupted run had saved before making it.

- **Everything restored.** The command exits 0 and clears the record.
- **A branch could not be restored.** The command exits 1 and keeps the record. Running `--abort` again gives the same answer until you decide what happens to that branch; see [Keep a branch that cannot be restored](#keep-a-branch-that-cannot-be-restored).
- **The landing was already verified.** The command prints `Kept the landing verified by an earlier reconciliation`, rolls nothing back, exits 1 and keeps the record. Finish with `spec-kitty consolidate --resume` instead.

Lane branches are never moved. For a Mission with a coordination topology, `--abort` also removes the coordination worktree unless the Mission's `meta.json` retains worktrees.

For the full description, see [Recover from an Interrupted Consolidation](recover-from-interrupted-merge.md#aborting-a-consolidation).

### Keep a branch that cannot be restored

A branch is `NOT restored` when it holds a commit this run did not record: a commit someone else added on top of the landing, or a move the interrupted run made without saving it. `--abort` will not move such a branch. When you want to keep its current commits, release it:

```bash
git log <restore-target>..<branch>
spec-kitty consolidate --abort --release-branch <branch> --release-reason "<why you keep it>"
```

Take `<restore-target>` from the report or the refusal. The released branch is left at its current commit and reported:

```text
  kept       <branch>  (released by operator: <why you keep it>; at <sha>; may contain this consolidation's unverified changes)
```

Review those changes afterwards: the kept commits can include what this consolidation landed without verifying it. A kept commit cannot ship a mission without its approved code: when the kept branch drops a work package's approved change (for example a commit of a lagging checkout's staged deletions), the next consolidation refuses with `APPROVED_CONTENT_MISSING` naming that work package. A kept mission branch that already carries a lane is also refused by the next consolidation, even with the lane's code intact, under either strategy (squash: its files read as belonging to no approved work package; merge: its commits do), so prefer `--abort` without a release when the branch can be restored. Every other branch is restored as usual. When nothing else is left unrestored, the command exits 0, clears the record, and its closing line names the kept branch instead of saying all branches were restored.

- **Repeatable.** Pass `--release-branch` once per branch. `--release-reason` is required and applies to all of them.
- **Only the record's own branches.** You can release the target branch, the mission branch or the coordination branch, never a lane branch.
- **Never a restorable branch.** If the branch can in fact be restored, `--abort` restores it and the release has no effect.
- **Bound to the commit.** The release is saved for the commit the branch is at when you run the command. If the branch moves afterwards, the release no longer applies and the branch is reported `NOT restored` again.
- **A release survives a failed abort.** If the same `--abort` cannot restore another branch, the release stays in the record. A later plain `spec-kitty consolidate --abort` still keeps the released branch while it sits at that commit, and reports it as `kept`.

If you do not want to keep the commits, move the branch yourself after reviewing them; spec-kitty never moves a commit it cannot prove is its own.

Misuse is refused before anything changes, with exit code 2 and `Error code: RELEASE_BRANCH_INVALID.`: `--release-branch` without `--abort`, without `--release-reason`, naming a lane branch or a branch the record does not know, or naming a branch that does not resolve to a commit.

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

### Origin is ahead of this clone (`ORIGIN_*` codes)

Before anything moves, `consolidate` (and `accept`) asks the remote that owns each branch it is about to trust, so a teammate's pushed rejection cannot land as done. A refusal prints the code, the branch and the command to run; nothing was moved. Re-run `spec-kitty consolidate` after the fix. A repository with no remote, or a branch that was never pushed, is not checked.

| Code | What it means | Fix |
|---|---|---|
| `ORIGIN_STATUS_STALE` | Origin has status events for this Mission that your clone lacks. | Run the printed `git pull` in the checkout that holds the branch (or `git fetch <remote> <branch>:<branch>`). With a consolidation record present, run `spec-kitty consolidate --abort` first, as the message says. |
| `ORIGIN_LANE_STALE` | An approved lane branch is behind origin, diverged from it, or missing here. | Behind: `git fetch <remote> <lane>` then `git -C <lane worktree> merge --ff-only <remote>/<lane>`. Missing: `git branch <lane> <remote>/<lane>`. Diverged: merge origin's lane in or rebase onto it, then push. Do not `git branch -f` a diverged lane. |
| `ORIGIN_UNREACHABLE` | The remote did not answer. The text says whether it timed out (maybe only slow: retry) or failed. | Retry, or check network access and credentials. |
| `ORIGIN_REMOTE_AMBIGUOUS` | Several remotes exist and none owns the branch. | `git config branch.<name>.remote <remote>`. |
| `ORIGIN_COMPARE_FAILED` | The remote answered but git could not compare the branch with it (shallow clone or damaged ref). | `git fetch --unshallow <remote>`, or repair the ref. |
| `ORIGIN_LANE_DIVERGED` | `spec-kitty agent action review` only: the reviewed lane diverged from origin. | Merge origin's lane in, or merge or rebase yours onto `<remote>/<lane>` and push. |

To go on anyway, `--origin-check warn` (or `SPEC_KITTY_ORIGIN_CHECK=warn`) prints each finding as a warning and continues. `--origin-check off` (or `SPEC_KITTY_ORIGIN_CHECK=off`) contacts nothing and accepts stale evidence: use it only when you cannot reach the remote and accept that a rejection your teammate pushed can land as done. `agent action review` has no flag and honors only the variable; `ORIGIN_LANE_DIVERGED` is lifted only by `SPEC_KITTY_ORIGIN_CHECK=warn`, never by a flag. Any other value of the variable enforces and prints a warning.

### Not synchronized with origin (only with --push)

```text
diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
```

This check runs only when `--push` is in effect. A plain `consolidate` does not need the target branch to match origin for push safety. (It does ask origin about the Mission's own status log and approved lanes: see [Origin is ahead](#origin-is-ahead-of-this-clone-origin_-codes).) The code means the local target branch is ahead of, behind or diverged from its tracking branch.

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

After landing, `consolidate` checks that the target holds exactly the approved work. When the check fails or cannot decide, the run restores the branches it moved and prints the rollback report that starts `Rollback to the pre-consolidation snapshot:`. If someone else committed on the target after the landing, that commit is kept: the target is reported `NOT restored ... moved by another actor`, and the record stays open (see [Keep a branch that cannot be restored](#keep-a-branch-that-cannot-be-restored)).

Read the divergence or reason. It names the WP, the lane and the paths. Correct the lane, then run `spec-kitty consolidate` or `--resume`.

- **A FAIL cannot be overridden.** Correct the content on the lane through a surviving WP.
- **Missing or contradictory attribution about a canceled WP** can be attested after you check by hand that the canceled content is absent or superseded:

  ```bash
  spec-kitty consolidate --attest-canceled-superseded WP03 --attest-reason "<what you checked>"
  ```

  The flag is repeatable, one WP per use, and `--attest-reason` is required. It never lifts a FAIL. A `--dry-run` does not apply it.

### A lane changed after its work package was approved

```text
Reconciliation refused (fail-closed) at claim time, before any change: LANE_MOVED_AFTER_APPROVAL: ...
```

`consolidate` only lands what review approved. It compares each code lane with the lane commit recorded when the WP was approved, and refuses before any branch moves. The message names the lane, the WP and the commit, and prints the commands to run.

| Code | What happened | What to do |
|---|---|---|
| `LANE_MOVED_AFTER_APPROVAL` | A commit was made on the lane after the WP was approved | Send the WP back with the printed `spec-kitty agent tasks move-task <WP> --to in_progress --mission <slug>`, have it reviewed, approve it again, then re-run `consolidate`. This also applies to a fix made after approval |
| `APPROVAL_STAMP_NOT_ON_LANE` | The lane was rewritten (amended or rebased) after approval | Same: send the WP back and approve it again |
| `APPROVAL_STAMP_MISSING` | The approval recorded no lane commit. Every approval made with a release before 4.0.0rc5 is in this state | Approve the WP again, or attest it (below) |

For `APPROVAL_STAMP_MISSING` only, you can attest that the lane as it stands is what was reviewed. Check the lane by hand first:

```bash
spec-kitty consolidate --mission <slug> --attest-approved-reviewed WP01 --attest-approved-reviewed WP02 --attest-reason "<what you checked>"
```

The attestation is recorded with your name and reason. It does not lift the other two codes, and `orchestrator-api consolidate-mission` has no attestation flag: use the CLI.

If a `--resume` is refused this way after an earlier attempt already moved the target, the message says so. Run `spec-kitty consolidate --abort` first: until then the local target holds content from the interrupted attempt.

On a lane that holds both an approved and a canceled WP, `--attest-canceled-superseded` no longer covers work done after the approval. The approved WP must be approved again as well.

The codes are defined in the [CLI reference](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes). The attribution rules and the full verdict table are in the [status model](../../../architecture/status-model.md#commit-attribution-stamp-policy_metadatalane_head).

### A branch moved without a record

```text
Error: Refusing to continue this consolidation: the merge record cannot explain where these branches are now (neither their restore target nor a tip this consolidation recorded or provably wrote):
  <branch>: restore target <sha>, live <sha>
Nothing was changed and the merge record is kept. To continue:
...
Error code: UNEXPLAINED_BRANCH_MOVE.
```

A re-run or `--resume` found a branch of an unfinished consolidation at a commit the merge record cannot account for. Typical causes: the earlier run was killed right after it moved the branch and before it recorded the move, or someone committed on the branch while the record was still open. The command stops before it moves anything, exits 1 and keeps the record. Running it again gives the same answer.

1. Inspect the commits the message names: `git log <restore-target>..<live>`.
2. If these commits should not stay, move the branch yourself; spec-kitty never moves a commit it cannot prove is its own.
3. To keep them, release the branch and clear the record: `spec-kitty consolidate --abort --release-branch <branch> --release-reason "<why>"` (see [Keep a branch that cannot be restored](#keep-a-branch-that-cannot-be-restored)). A release keeps every commit the `git log` listed on the branch, including any change of this consolidation that was never verified; the next consolidation still verifies them, and refuses with `APPROVED_CONTENT_MISSING` if one dropped approved code. Then start the consolidation again.

A resume whose landing was already verified, with the target still at that commit, is not refused; it finishes the cleanup.

Known cases that refuse this way, even though nobody else touched the branch:

- The run was killed right after a commit it makes without first saving where it moves the branch: the mission-number bake commit in the repository root checkout, or a plain status commit on the target.
- You ran `git pull` (or committed) on the target after a hard kill, before re-running or aborting.

Not covered yet: `orchestrator-api`'s planning-closeout path reports this refusal as `PREFLIGHT_FAILED` without the code, and `spec-kitty consolidate --dry-run` does not predict it.

### Exit code 75: the landing stands

Exit code 75 with `Error code: COORD_MOVED_AFTER_LANDING.` means the landing is verified, but a commit reached the coordination branch (or the mission branch) before it could be deleted. The branch is kept and nothing is rolled back. For a coordination branch, review the late commits with the `git log` command in the message, then run `spec-kitty consolidate --resume`.

See [Exit code 75](recover-from-interrupted-merge.md#exit-code-75-the-landing-stands-the-cleanup-did-not-finish) for the mission-branch variant.

## See Also

- [How to Merge a Mission](../missions/merge-mission.md): the normal consolidation flow
- [Accept and Merge](../missions/accept-and-merge.md): validation before consolidation
- [Handle Dependencies](../missions/handle-dependencies.md): WP dependency management
- [CLI reference: exit codes and refusal codes](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes)
- [Git workflow](../../../architecture/git-workflow.md#4-consolidated): what each consolidation step does
