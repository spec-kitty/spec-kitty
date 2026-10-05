---
title: How to Merge a Mission
description: 'How to merge a mission with Spec Kitty 3.2: land approved work packages on the local target branch with spec-kitty consolidate, preview it, and choose cleanup.'
doc_status: active
updated: '2026-10-05'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/missions/accept-and-merge.md
- docs/guides/how-to/missions/keep-main-clean.md
- docs/guides/how-to/missions/review-work-package.md
- docs/guides/how-to/collaboration/run-an-autonomous-mission.md
- docs/guides/how-to/governance/use-retrospective-learning.md
---
# How to Merge a Mission

Use this guide to land a Mission's approved work packages on its target branch with `spec-kitty consolidate`.

`consolidate` lands the lane branches on the mission branch, then lands the mission branch on the **local** target branch. It never publishes to origin unless you pass `--push`. Publish through a topic branch and a pull request.

## Prerequisites

- Every WP is `approved` or `done`.
- You ran acceptance. See [Accept and Merge](accept-and-merge.md).
- The repository root checkout is on the target branch and has no uncommitted changes. Lane worktrees have no uncommitted changes either, unless you keep them with `--keep-worktree`.

## Quick Start

Run the command from the repository root checkout.

In your agent:

```text
/spec-kitty.consolidate
```

In your terminal:

```bash
spec-kitty consolidate --mission 015-user-authentication
```

`--mission` names the Mission; it accepts the slug, the `mid8` or the Mission ID. The command was renamed from `spec-kitty merge`, and the old name now exits with an error. Replace it in scripts and notes.

If a run stops, see [How to Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md).

## Preview with Dry-Run

```bash
spec-kitty consolidate --mission 015-user-authentication --dry-run
```

A dry run changes nothing. It prints the resolved plan as JSON: the strategy, the target branch, the mission branch, the lanes, whether branches and worktrees will be deleted, whether `--push` is set, and the mission number the run would assign. Add `--json` for plain JSON output; `--json` works only with `--dry-run`.

The dry run stops with a blocker, and exits 1, when the real run would refuse for a reason it can check in advance. The blockers include a review-artifact conflict and `TARGET_BRANCH_CONTENT_CONFLICT`. See [Target-Branch Content Conflicts During Squash](../recovery/troubleshoot-merge.md#target-branch-content-conflicts-during-squash).

## Strategies

`--strategy` sets how the mission branch lands on the target branch. The lane-to-mission step always uses merge commits.

| Strategy | Effect |
| --- | --- |
| `squash` | Lands the mission branch as one commit. This is the default. |
| `merge` | Lands the mission branch with a merge commit. |
| `rebase` | Rebases the mission branch onto the target branch, then advances the target branch to the result. |

Values are lower-case:

```bash
spec-kitty consolidate --mission 015-user-authentication --strategy merge
```

To set a project default, add this to `.kittify/config.yaml`:

```yaml
merge:
  strategy: merge
```

The order is: `--strategy`, then `merge.strategy`, then `squash`. A value outside `merge`, `squash` and `rebase` in the config file is an error. A resumed run keeps the strategy of the interrupted run.

## Target Branch

By default `consolidate` lands on the Mission's recorded target branch. Override it only when you intend a different destination:

```bash
spec-kitty consolidate --mission 015-user-authentication --target develop
```

## Cleanup Options

After a successful landing, `consolidate` removes the lane worktrees and deletes the lane branches. Each flag pair overrides that default for one resource:

```bash
spec-kitty consolidate --mission 015-user-authentication --keep-worktree
spec-kitty consolidate --mission 015-user-authentication --keep-branch
spec-kitty consolidate --mission 015-user-authentication --keep-worktree --keep-branch
```

`--remove-worktree` and `--delete-branch` state the default explicitly. They also override a Mission's retention policy.

### Mission Retention Policy

A Mission can record a standing retention policy in its `meta.json`: `retain_branches: true`, `retain_worktrees: true`, or both. The policy is absent unless you set it, so a Mission that never opts in keeps the default cleanup.

Effective cleanup follows this order:

1. An explicit flag (`--keep-branch` or `--delete-branch`, `--keep-worktree` or `--remove-worktree`).
2. The `meta.json` retention policy.
3. The default: delete branches and remove worktrees.

`retain_branches` acts as `--keep-branch`, and `retain_worktrees` acts as `--keep-worktree`. Retention is never silent:

- With no flag and a retaining policy, `consolidate` keeps the resource and prints a warning that names `meta.json` as the source.
- An explicit `--delete-branch` or `--remove-worktree` against a retaining Mission proceeds and prints a notice that the flag overrode the policy.
- A corrupt `meta.json` stops the run with an error. A retention value that is not a boolean counts as retain and prints a warning.
- `--dry-run` shows the resolved decision, with a `retention` object that names its source.

For a Mission with a coordination topology, the coordination branch, its worktree and its marker in `meta.json` are kept or removed together. They are removed only when branches are deleted **and** worktrees are removed. Keeping either one keeps all three. `--abort` follows the same rule for the coordination worktree.

The private scratch worktree that `consolidate` uses under `.kittify/runtime/merge/<mission_id>/workspace` is not a retained resource. It is always removed.

#### Declaring Retention at Creation

Set the policy when you create the Mission:

```bash
spec-kitty agent mission create "<slug>" --retain-branches --retain-worktrees ...
```

## Publish the Result

`consolidate` lands on the local target branch only. Publish through a topic branch and a pull request. See [When Local `main` Is Not Publishable](accept-and-merge.md#when-local-main-is-not-publishable) and [Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md).

`--push` publishes to origin after the local landing. Use it only where your repository's workflow allows direct pushes to the target branch. With `--push`, a local target branch that is ahead of, behind or diverged from its tracking branch is refused with `TARGET_BRANCH_NOT_SYNCHRONIZED`. See [How to Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md#not-synchronized-with-origin-only-with---push).

## After Merge

Before you call the Mission done, run the mission review, check the retrospective, and read its findings. See [After Consolidation](accept-and-merge.md#after-consolidation).

## Command Reference

| Flag | What it does | Default |
| --- | --- | --- |
| `--mission <slug>` | Names the Mission | Resolved from the current branch when possible; otherwise the command asks for `--mission` |
| `--strategy` | `merge`, `squash` or `rebase` | `squash` |
| `--target <branch>` | Target branch for the landing | The Mission's recorded target branch |
| `--delete-branch` / `--keep-branch` | Delete or keep lane branches | The retention policy, else delete |
| `--remove-worktree` / `--keep-worktree` | Remove or keep lane worktrees | The retention policy, else remove |
| `--push` | Publish to origin after the local landing | No push |
| `--dry-run` | Show the plan without changing anything | Off |
| `--json` | JSON output, with `--dry-run` only | Off |
| `--resume` | Continue an interrupted run | Off |
| `--abort` | Restore the branches the run moved and clear the record | Off |
| `--yes`, `-y` | Proceed after warnings without prompts | Off |
| `--skip-review-artifact-check` | Bypass the review-artifact consistency gate. Requires `--note "<reason>"`, which is recorded as override evidence | Off |
| `--skip-lanes` | Complete a direct-on-target Mission whose `lanes.json` is genuinely absent | Off |
| `--allow-sparse-checkout` | Proceed when legacy sparse-checkout state is detected | Off |
| `--attest-canceled-superseded <WP>` | Attest, after checking by hand, that a canceled WP's content is absent or superseded. Repeatable, requires `--attest-reason "<what you checked>"`, never lifts a FAIL | Off |
| `--attest-approved-reviewed <WP>` | Attest, after checking the lane by hand, that an approval with no recorded lane commit (`APPROVAL_STAMP_MISSING`, any approval made before 4.0.0rc5) covers the lane as it stands. Repeatable, requires `--attest-reason "<what you checked>"`. Does not lift `LANE_MOVED_AFTER_APPROVAL` | Off |

Full reference: [CLI Commands](../../../api/cli-commands.md#spec-kitty-consolidate). Exit codes and refusal codes: [CLI reference](../../../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes).

## See Also

- [Accept and Merge](accept-and-merge.md): validation before consolidation
- [Keep Main Clean](keep-main-clean.md): choose a target branch without changing the planning location
- [Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md): autonomous run and focused pull request path
- [How to Troubleshoot Merge Issues](../recovery/troubleshoot-merge.md): resume, abort and refusals
- [Recover from an Interrupted Consolidation](../recovery/recover-from-interrupted-merge.md): the record, the rollback and the exit codes

## Background

- [Execution Lanes](../../../architecture/execution-lanes.md): how worktrees work
- [Git Worktrees](../../../architecture/git-worktrees.md): git worktree fundamentals
- [Git workflow](../../../architecture/git-workflow.md#4-consolidated): what each consolidation step does

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md): complete workflow walkthrough
