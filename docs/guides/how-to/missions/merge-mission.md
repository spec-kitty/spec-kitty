---
title: How to Merge a Mission
description: 'How to merge a mission with Spec Kitty 3.2: Use this guide to merge completed work packages from a Spec Kitty mission into its target branch.'
doc_status: active
updated: '2026-08-31'
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

Use this guide to merge completed work packages from a Spec Kitty mission into its target branch.

## Prerequisites

- All WPs have been reviewed and are `approved` or `done`
- All resolved execution worktrees have no uncommitted changes
- You have run `/spec-kitty.accept` to validate the mission is ready

## Quick Start

From any execution workspace or from the repository root checkout with the `--mission` flag:

In your agent:

```text
/spec-kitty.merge
```

Or in your terminal:

```bash
spec-kitty merge
```

Or from the repository root checkout:

```bash
spec-kitty merge --mission 015-user-authentication
```

## Pre-flight Validation

Before merging, spec-kitty runs automatic pre-flight checks:

1. **Workspace cleanliness**: All resolved execution workspaces must have no uncommitted changes
2. **Missing workspaces**: All WPs defined in tasks must have execution workspaces created if they are expected to merge
3. **Target divergence**: The mission's target branch should not be behind origin

Example pre-flight output when validation passes:

```
Pre-flight Check

┌─────────┬────────┬───────┐
│ WP      │ Status │ Issue │
├─────────┼────────┼───────┤
│ WP01    │ ✓      │       │
│ WP02    │ ✓      │       │
│ WP03    │ ✓      │       │
│ Target  │ ✓      │ Up to date │
└─────────┴────────┴───────┘

Pre-flight passed. Ready to merge.
```

Example when validation fails:

```
Pre-flight Check

┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ WP     ┃ Status ┃ Issue                                                      ┃
┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ WP01   │ ✓      │                                                            │
│ WP02   │ ✓      │                                                            │
│ WP03   │ ✗      │ Uncommitted changes in                                     │
│        │        │ 018-merge-preflight-documentation-lane-b                   │
│ WP04   │ ✗      │ Uncommitted changes in                                     │
│        │        │ 018-merge-preflight-documentation-lane-c                   │
│ Target │ ✓      │ Up to date                                                 │
└────────┴────────┴────────────────────────────────────────────────────────────┘

Pre-flight failed. Fix these issues before merging:

  1. Uncommitted changes in 018-merge-preflight-documentation-lane-b
  2. Uncommitted changes in 018-merge-preflight-documentation-lane-c
```

### Fixing Pre-flight Failures

| Issue | Fix |
|-------|-----|
| Uncommitted changes in a workspace | `cd <workspace path printed by spec-kitty implement>` then commit or stash |
| Missing workspace for WP## | `spec-kitty implement WP##` |
| Target is behind origin | `git checkout <target-branch> && git pull` |
| `TARGET_BRANCH_NOT_SYNCHRONIZED` while local `main` is ahead or diverged | Inspect divergence, then open a focused PR from `kitty/mission-<mission-slug>` or `kitty/pr/<mission-slug>-to-main` instead of pushing local `main` |
| `TARGET_BRANCH_CONTENT_CONFLICT` — the default squash would clobber newer target-branch content | Reconcile the mission branch against the current target, resolve the listed paths, then rerun. See [Target-Branch Content Conflicts During Squash](../recovery/troubleshoot-merge.md#target-branch-content-conflicts-during-squash) |

### Focused PR for Autonomous Local Runs

`spec-kitty merge` stops before mutating merge state when the target branch is
not synchronized with its tracking branch:

```text
Error: target branch is not synchronized with its tracking branch.
  diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
  branch_or_work_package: main
  violated_invariant: local_target_branch_must_match_tracking_branch
```

For autonomous local runs, local `main` may be ahead of or diverged from
`origin/main` because the run created planning, status, review, and orchestration
commits. Do not reset, rebase, force-push, or push local `main` as remediation
for this diagnostic.

Inspect the divergence first:

```bash
git fetch origin main
git log --oneline --left-right --cherry-pick main...origin/main
git diff --name-only origin/main...main
```

If the mission branch already contains the approved result, open the PR directly
from that branch:

```bash
git push -u origin kitty/mission-<mission-slug>
gh pr create --base main --head kitty/mission-<mission-slug> --fill
```

If you want a dedicated branch for the PR, create it from the mission branch:

```bash
git switch -c kitty/pr/<mission-slug>-to-main kitty/mission-<mission-slug>
git push -u origin kitty/pr/<mission-slug>-to-main
gh pr create --base main --head kitty/pr/<mission-slug>-to-main --fill
```

Prefer squash-merge for autonomous runs that accumulated many orchestration
commits:

```bash
gh pr merge --squash --delete-branch
```

See [Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md) for the full
end-to-end workflow.

## Preview with Dry-Run

See what would happen without executing:

```bash
spec-kitty merge --dry-run
```

Example output:

```
Lane-based mission detected: 4 work packages across 3 execution workspaces
  - WP01: 018-merge-preflight-documentation-lane-a
  - WP02: 018-merge-preflight-documentation-lane-a
  - WP03: 018-merge-preflight-documentation-lane-b
  - WP04: 018-merge-preflight-documentation-lane-c

Validating all execution workspaces...
✓ All execution workspaces validated
Mission Merge

Dry run - would execute:
  1. git checkout <target-branch>
  2. git pull --ff-only
  3. git merge --no-ff kitty/mission-018-merge-preflight-documentation
  4. git worktree remove /.../.worktrees/018-merge-preflight-documentation-lane-a
  5. git worktree remove /.../.worktrees/018-merge-preflight-documentation-lane-b
  6. git worktree remove /.../.worktrees/018-merge-preflight-documentation-lane-c
  7. git branch -d kitty/mission-018-merge-preflight-documentation-lane-a
  8. git branch -d kitty/mission-018-merge-preflight-documentation-lane-b
  9. git branch -d kitty/mission-018-merge-preflight-documentation-lane-c
  10. git branch -d kitty/mission-018-merge-preflight-documentation
```

### Conflict Forecasting

Dry-run also predicts potential conflicts:

```
Conflict Forecast

Found 2 potential conflict(s): 1 auto-resolvable, 1 manual

May require manual resolution:
┌─────────────────────────────────────┬───────────┬────────────┐
│ File                                │ WPs       │ Confidence │
├─────────────────────────────────────┼───────────┼────────────┤
│ docs/guides/merge-feature.md        │ WP01, WP03│ possible   │
└─────────────────────────────────────┴───────────┴────────────┘

Auto-resolvable (status files):
┌────────────────────────────────────────────────────────────┬───────────┐
│ Status File                                                │ WPs       │
├────────────────────────────────────────────────────────────┼───────────┤
│ kitty-specs/018-merge-preflight-documentation/tasks/WP01.md│ WP01, WP02│
└────────────────────────────────────────────────────────────┴───────────┘

Prepare to resolve 1 conflict(s) manually during merge.
```

**Status files** (WP prompt files in `kitty-specs/*/tasks/*.md`) are auto-resolved by taking the more advanced lane status and merging history entries chronologically.

## Merge Strategies

### Default (Merge Commits)

Creates a merge commit for each WP, preserving full history:

```bash
spec-kitty merge
```

Each WP gets a commit message like: `Merge WP01 from 015-user-authentication`

### Squash

Squashes each WP into a single commit (cleaner history, loses per-commit detail):

```bash
spec-kitty merge --strategy squash
```

### Rebase

Not supported for multi-workspace missions due to the complexity of rebasing multiple dependent branches. Use `merge` or `squash` instead.

## Cleanup Options

By default, merge removes all resolved execution worktrees and deletes their branches after successful merge.

### Keep Worktrees

Keep worktrees for reference after merge:

```bash
spec-kitty merge --keep-worktree
```

### Keep Branches

Keep branches after merge (useful for PR workflows):

```bash
spec-kitty merge --keep-branch
```

### Keep Both

```bash
spec-kitty merge --keep-worktree --keep-branch
```

### Explicit Cleanup

To explicitly remove worktrees and delete branches (the default behavior):

```bash
spec-kitty merge --remove-worktree --delete-branch
```

These flags are useful when you want to override a config default that keeps artifacts.

### Mission Retention Policy

A mission can declare a standing retention policy in its `meta.json` — `retain_branches: true` and/or `retain_worktrees: true` — instead of relying on an operator remembering `--keep-branch`/`--keep-worktree` on every merge. Mint it at mission creation (see [Declaring Retention at Creation](#declaring-retention-at-creation)); it is absent by default, so missions that never opt in keep today's default cleanup behavior unchanged.

Effective cleanup resolves with this precedence:

**explicit CLI flag (`--keep-branch`/`--delete-branch`, `--keep-worktree`/`--remove-worktree`) > `meta.json` retention policy > default (delete/remove)**

The mapping onto the long-standing flags is 1:1: `retain_branches` resolves to an effective `--keep-branch`; `retain_worktrees` resolves to an effective `--keep-worktree`.

**Fail-closed, and never silent:**

- When no cleanup flag is passed and the mission's policy requests retention, merge **retains** the resource and prints an operator-visible warning naming the source (`meta.json`).
- When an operator explicitly passes `--delete-branch` (or `--remove-worktree`) against a retaining mission, the deletion proceeds — but a **notice** is printed recording that the explicit flag overrode the mission's retention policy. Retention is never silently discarded.
- A corrupt `meta.json` aborts the merge with a clear error rather than falling through to delete.
- A malformed (non-boolean) retention value is treated as retaining, with a warning — never silently coerced to "delete".
- `spec-kitty merge --dry-run` previews the **resolved** cleanup decision: for a retaining mission with no cleanup flags it reports `delete_branch: false` / `remove_worktree: false` and a `retention` provenance object, so you can confirm the policy is honored before running the real merge.

**Coordination topology is retained/torn down as one unit.** For a coordination-topology mission, the coordination branch, its worktree, and its `coordination_branch` marker in `meta.json` are a single consistency triple. They are only torn down when **both** branches and worktrees resolve to delete/remove; if either resource resolves to "retain" (via meta.json or `--keep-*`), the whole coordination triple is kept together. This prevents a partial-retention request (e.g. `retain_branches: true` alone) from stranding a half-torn coordination state — the marker is never flattened while its worktree survives, and vice versa. `spec-kitty merge --abort` honors the same coupled decision for the coordination worktree during rollback.

**The internal merge scratch worktree is not a retained resource.** `spec-kitty merge` uses a private scratch worktree under `.kittify/runtime/merge/<id>/workspace` as working plumbing during the merge — distinct from a mission's lane worktrees. It is always cleaned up unconditionally at the end of a merge, even when `retain_worktrees: true` is in effect.

#### Declaring Retention at Creation

Opt a mission into retention when creating it:

```bash
spec-kitty agent mission create "<slug>" --retain-branches --retain-worktrees ...
```

This mints `retain_branches`/`retain_worktrees` into the mission's `meta.json` at creation time, so the policy is machine-readable from the start rather than living only as prose a merge cannot read.

## Push After Merge

Push to origin immediately after merge:

```bash
spec-kitty merge --push
```

## Merge from the repository root checkout

If you're in the repository root checkout and want to merge a mission:

```bash
spec-kitty merge --mission 015-user-authentication
```

This detects all WP worktrees for that mission and merges them in dependency order.

## target branch

By default, Spec Kitty merges into the mission's recorded target branch. Override it only when you intentionally need a different destination:

```bash
spec-kitty merge --target develop
```

## Dependency-Ordered Merging

WPs are merged in dependency order based on the `dependencies` field in their frontmatter:

```yaml
---
work_package_id: "WP03"
dependencies: ["WP01", "WP02"]
---
```

The merge command reads these dependencies and ensures:
- WP01 merges first (no dependencies)
- WP02 merges second (depends on WP01)
- WP03 merges last (depends on WP01 and WP02)

## Interrupted Merge Recovery

If a merge is interrupted (crash, conflict, network issue), use `--resume` to continue:

```bash
spec-kitty merge --resume
```

## See Also

- [Keep Main Clean](keep-main-clean.md) - Choose a target branch without changing planning location
- [Accept and Merge](accept-and-merge.md) - Shorter end-to-end merge flow
- [Run an Autonomous Mission](../collaboration/run-an-autonomous-mission.md) - Autonomous run and focused-PR fallback

This picks up where the merge left off, using the saved state in `.kittify/merge-state.json`.

To abandon an interrupted merge and clear state:

```bash
spec-kitty merge --abort
```

This removes the merge state file and lets you start fresh.

For detailed troubleshooting including conflict resolution and error recovery, see [Accept and Merge](accept-and-merge.md#troubleshooting).

## After Merge

Complete the following three steps before declaring the mission done.

**1. Mission review** — run the post-merge mission review to confirm spec→code fidelity and FR
coverage:

```bash
# In your agent:
/spec-kitty-mission-review
```

**2. Author or verify the retrospective** — under default policy the record was written during
merge. Verify with:

```bash
cat .kittify/missions/$(jq -r .mission_id kitty-specs/<slug>/meta.json)/retrospective.yaml
```

If absent (older mission predating 3.2.0), author it:

```bash
spec-kitty retrospect create --mission <handle>
```

**3. Surface findings**:

```bash
spec-kitty retrospect summary                              # cross-mission view (read-only)
spec-kitty agent retrospect synthesize --mission <handle>  # inspect proposals (dry-run by default)
spec-kitty agent retrospect synthesize --mission <handle> --apply <id>  # apply a proposal
```

For the full command reference, see
[How to Use Retrospective Learning](../governance/use-retrospective-learning.md).

---

## Command Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--strategy` | Merge strategy: `merge`, `squash` (rebase not supported for multi-workspace missions) | `merge` |
| `--delete-branch` / `--keep-branch` | Delete lane and mission branches after merge. Unset defers to the mission's `meta.json` `retain_branches` policy (see [Mission Retention Policy](#mission-retention-policy)); passing either flag always wins | Delete (unless `retain_branches: true` in `meta.json`) |
| `--remove-worktree` / `--keep-worktree` | Remove resolved execution worktrees after merge. Unset defers to the mission's `meta.json` `retain_worktrees` policy; passing either flag always wins | Remove (unless `retain_worktrees: true` in `meta.json`) |
| `--push` | Push to origin after merge | No push |
| `--target` | target branch to merge into | `main` |
| `--dry-run` | Show what would be done without executing | - |
| `--mission` | Mission slug (when running from main) | Auto-detect |
| `--resume` | Resume an interrupted merge | - |
| `--abort` | Abort and clear merge state | - |

Full CLI reference: [CLI Commands](../../../api/cli-commands.md)

## See Also

- [Accept and Merge](accept-and-merge.md#troubleshooting) - Recovery and conflict resolution
- [Accept and Merge](accept-and-merge.md) - Mission validation before merge
- [Execution Lanes](../../../architecture/execution-lanes.md) - How worktrees work
- [Review Work Packages](review-work-package.md) - WP review process

## Background

- [Execution Lanes](../../../architecture/execution-lanes.md) - How worktrees work
- [Git Worktrees](../../../architecture/git-worktrees.md) - Git worktree fundamentals

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
