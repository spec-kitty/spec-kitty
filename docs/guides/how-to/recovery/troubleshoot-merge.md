---
title: How to Troubleshoot Merge Issues
description: 'How to troubleshoot merge issues with Spec Kitty 3.2: Use this guide to recover from interrupted merges, resolve conflicts, and fix pre-flight failures.'
doc_status: active
updated: '2026-09-22'
audience: docs/context/audience/external/project-owner.md
type: how-to
related:
- docs/guides/how-to/missions/accept-and-merge.md
- docs/guides/how-to/missions/handle-dependencies.md
- docs/guides/how-to/missions/merge-mission.md
---
# How to Troubleshoot Merge Issues

Use this guide to recover from interrupted merges, resolve conflicts, and fix pre-flight failures.

## Quick Reference

```
Merge failed?
├── Pre-flight failed → See "Pre-flight Failures" below
├── Conflicts during merge → See "Resolve Merge Conflicts" below
├── Interrupted (terminal closed) → spec-kitty merge --resume
└── Want to start over → spec-kitty merge --abort
```

## Resume an Interrupted Merge

If your merge was interrupted (terminal closed, system crash, etc.), resume from where it stopped:

```bash
spec-kitty merge --resume
```

Example output:

```
Resuming merge of 017-my-feature
  Progress: 1/2 lanes
  Remaining: lane-b

Merging lane-b (kitty/mission-017-my-feature-lane-b)...
✓ lane-b merged
```

### Understanding merge state

Merge progress is saved in `.kittify/merge-state.json`:

```json
{
  "feature_slug": "017-my-feature",
  "target_branch": "main",
  "wp_order": ["WP01", "WP02", "WP03", "WP04", "WP05"],
  "completed_wps": ["WP01", "WP02"],
  "current_wp": "WP03",
  "has_pending_conflicts": false,
  "strategy": "merge",
  "started_at": "2026-01-18T10:00:00+00:00",
  "updated_at": "2026-01-18T10:15:00+00:00"
}
```

| Field | Description |
|-------|-------------|
| `feature_slug` | Legacy merge-state field for the mission being merged |
| `target_branch` | Branch being merged into |
| `wp_order` | Ordered list of WPs to merge |
| `completed_wps` | WPs that have been successfully merged |
| `current_wp` | WP being merged when interrupted (if any) |
| `has_pending_conflicts` | True if git merge conflicts exist |
| `strategy` | Merge strategy (merge, squash, rebase) |
| `started_at` | When merge began |
| `updated_at` | Last state update |

### When to Use --resume

Use `--resume` when:
- Terminal closed during merge
- System crashed mid-merge
- You manually fixed conflicts and want to continue

Do **not** use `--resume` if you want to:
- Change merge strategy
- Merge a different mission
- Start fresh after major changes

## Abort and Start Fresh

Clear merge state and abort any in-progress git merge:

```bash
spec-kitty merge --abort
```

Example output:

```
✓ merge state cleared for 017-my-feature
  Progress was: 2/5 WPs complete
✓ Git merge aborted
```

After aborting, you can start a new merge:

```bash
spec-kitty merge --mission 017-my-feature
```

### What --abort Clears

1. **merge state file** (`.kittify/merge-state.json`) - Removed
2. **Git merge state** - If git is mid-merge, runs `git merge --abort`

What it does **not** do:
- Does not delete worktrees (they remain as-is)
- Does not delete branches (completed WPs stay merged)
- Does not revert already-merged commits

### When to Use --abort

Use `--abort` when:
- You want to change merge strategy
- Something went fundamentally wrong
- You need to make changes before re-merging

## Resolve Merge Conflicts

### Status File Conflicts (Automatic)

Conflicts in WP prompt files (`kitty-specs/*/tasks/*.md`) are automatically resolved:

- **Lane field**: Takes the more advanced status (done > approved > in_review > for_review > in_progress > claimed > planned)
- **Checkboxes**: Takes checked [x] over unchecked [ ]
- **History array**: Merges both sides chronologically, removes duplicates

You don't need to do anything for these files - they're auto-resolved and staged.

### When Auto-Resolution Fails

If auto-resolution fails (unusual file structure, corrupted content):

1. Open the conflicted file
2. Find conflict markers:
   ```
   <<<<<<< HEAD
   lane: "done"
   =======
   lane: "for_review"
   >>>>>>> kitty/mission-017-feature-lane-b
   ```
3. Choose the appropriate value (usually "done" for lane)
4. Remove conflict markers
5. Save and stage:
   ```bash
   git add kitty-specs/017-feature/tasks/WP03-guide.md
   ```
6. Resume merge:
   ```bash
   spec-kitty merge --resume
   ```

### Code Conflicts (Manual)

For conflicts in source code files:

1. Check which files have conflicts:
   ```bash
   git status
   ```
   Look for "both modified" files.

2. Open each conflicted file and resolve:
   ```
   <<<<<<< HEAD
   def existing_function():
       return "old behavior"
   =======
   def existing_function():
       return "new behavior"
   >>>>>>> kitty/mission-017-feature-lane-a
   ```

3. Edit to combine both changes appropriately:
   ```python
   def existing_function():
       return "combined behavior"
   ```

4. Stage resolved files:
   ```bash
   git add src/path/to/file.py
   ```

5. Resume merge:
   ```bash
   spec-kitty merge --resume
   ```

### Target-Branch Content Conflicts During Squash

The default squash strategy fails closed when both the mission branch and a
newer target-branch commit changed the same ordinary source hunk. Dry-run reports
the same condition before the target ref can move:

```text
diagnostic_code: TARGET_BRANCH_CONTENT_CONFLICT
mission_branch: kitty/mission-017-my-feature
target_branch: main
conflicting_path: src/specify_cli/lanes/merge.py
```

This protects target-branch hotfixes and concurrent mission landings. Spec Kitty
does not choose either side automatically. Update the mission branch against the
current target, resolve the listed files on the mission branch, run the relevant
tests, and check readiness again:

```bash
git checkout kitty/mission-017-my-feature
git merge main
# Resolve and commit the named conflicts.
spec-kitty merge --mission 017-my-feature --dry-run
spec-kitty merge --mission 017-my-feature
```

The failed attempt does not advance the target ref, mark work packages done,
write the retrospective, or remove lane branches and worktrees. Registered Spec
Kitty artifact merge drivers and the target-newer planning-artifact policy still
handle their own governed paths.

### Gate Artifact Verdict Conflicts (Fail-Closed)

If a merge stops with a message like this and leaves `acceptance-matrix.json`
(or the issue matrix) conflicted:

```
row 'FR-042': verdict field 'pass_fail' diverged on both sides with no common base value (target/ours='pass', incoming/theirs='fail')
```

it means **two lanes recorded conflicting verdicts** for the same criterion or
invariant — one graded it `pass`, the other `fail`. Spec Kitty refuses to guess
(a wrong guess would silently corrupt an acceptance record), so it fails closed
and hands the decision to you. This is intentional, not a bug.

**Fix**: open the named matrix, find the row the message names (`FR-042` above),
decide the correct verdict yourself, write that single value in place of the git
conflict markers, save, stage, and resume:

```bash
git add kitty-specs/<mission>/acceptance-matrix.json
spec-kitty merge --resume
```

A scaffold/placeholder verdict (`pending`, `unknown`) never triggers this — it
yields to the graded side automatically. Only two genuinely-graded, disagreeing
verdicts stop the merge.

### Conflict Resolution Tips

- **Read both sides**: Understand what each WP was trying to do
- **Check imports**: Import conflicts often need combining, not choosing
- **Test after resolve**: Run tests before resuming to catch integration issues
- **When in doubt, abort**: `spec-kitty merge --abort` and merge manually

## Pre-flight Validation Failures

Pre-flight runs before any merge operations. All issues are shown upfront.

### Uncommitted Changes

```
Pre-flight failed. Fix these issues before merging:
  1. Uncommitted changes in kitty/mission-017-feature-lane-a
```

**Fix**: Commit or stash changes in that execution workspace:

```bash
cd <workspace path printed by spec-kitty implement>
git add -A
git commit -m "Complete WP02 implementation"
```

Or stash if you're not ready to commit:

```bash
cd <workspace path printed by spec-kitty implement>
git stash
```

### Missing Worktree

```
Pre-flight failed. Fix these issues before merging:

  1. Missing worktree for lane-b. Expected at 017-feature-lane-b. Run: spec-kitty agent action implement WP03
```

**Fix**: Create the missing worktree using the agent workflow command:

```bash
spec-kitty agent action implement WP03
```

### target branch not synchronized with origin

```
Error: target branch is not synchronized with its tracking branch.
  diagnostic_code: TARGET_BRANCH_NOT_SYNCHRONIZED
  branch_or_work_package: main
  violated_invariant: local_target_branch_must_match_tracking_branch
```

`spec-kitty merge` stops before mutating merge state when the target branch is ahead of, behind, or diverged from its tracking branch.

First inspect the branch state:

```bash
git fetch origin main
git log --oneline --left-right --cherry-pick main...origin/main
git diff --name-only origin/main...main
```

If local `main` is **ahead** or **diverged**, do not push it just to satisfy the preflight. Ahead commits may include Spec Kitty orchestration history, agent state commits, worktree bookkeeping, unrelated missions, or other local-only work. Use the focused PR path from the diagnostic unless you verified every ahead commit belongs on `main` now:

```bash
git switch -c kitty/pr/<mission-slug>-to-main kitty/mission-<mission-slug>
git push -u origin kitty/pr/<mission-slug>-to-main
gh pr create --base main --head kitty/pr/<mission-slug>-to-main
```

Only direct-push `main` after reviewing both commits and changed paths, and only when the human explicitly wants those commits published.

If local `main` is only **behind**, update it from the tracking branch after reviewing remote-only commits, then retry the merge from any checkout where the mission resolves correctly.

### Branch Does Not Exist

```
Pre-flight failed. Fix these issues before merging:
  1. Branch kitty/mission-017-feature-lane-a does not exist
```

**Fix**: This usually means the worktree was manually deleted without the branch. Recreate:

```bash
spec-kitty implement WP02
```

---

## Error Message Reference

| Error Message | Cause | Solution |
|--------------|-------|----------|
| `Error: Already on <branch> branch.` | Running merge from the target branch without `--mission` | Use `spec-kitty merge --mission <slug>` |
| `Error: No worktrees found for feature '<slug>'.` | Mission has no execution workspaces or the slug is wrong | Check the slug, then run `spec-kitty agent action implement WP01` |
| `Cannot merge: WP workspaces not ready` | One or more execution workspaces are not merge-ready | Fix the listed workspace errors, then retry merge |
| `Worktree <name> has uncommitted changes` | Specific worktree has unstaged/uncommitted work | `cd .worktrees/<name>` then commit or stash |
| `Uncommitted changes in <worktree-name>` | Worktree has uncommitted changes (pre-flight) | Commit or stash changes in that worktree |
| `Error: Working directory has uncommitted changes.` | Legacy merge run from a dirty worktree | Commit or stash changes, then retry merge |
| `Target repository at <path> has uncommitted changes.` | repository root checkout has uncommitted work | Commit or stash in the repository root checkout |
| `Missing worktree for WP##. Expected at <path>. Run: spec-kitty agent action implement WP##` | The resolved execution workspace for that WP does not exist yet | Run `spec-kitty agent action implement WP##` |
| `Branch <branch> does not exist` | Git branch was deleted manually | Recreate worktree with `spec-kitty implement WP##` |
| `TARGET_BRANCH_NOT_SYNCHRONIZED` | target branch is ahead of, behind, or diverged from its tracking branch | Inspect commits and paths; use the focused PR path for ahead/diverged local target branches unless every ahead commit is intentionally ready for `main` |
| `TARGET_BRANCH_CONTENT_CONFLICT` | Default squash integration found ordinary content changed differently on the mission and target branches | Update the mission branch against the target, resolve the listed paths, then rerun `spec-kitty merge --dry-run` |
| `<branch> is N commit(s) behind origin. Run: git checkout <branch> && git pull` | Legacy target branch staleness diagnostic | Review remote-only commits, then update the local target branch |
| `Warning: Could not fast-forward <branch>.` | Fast-forward failed, conflicts likely | Resolve conflicts manually |
| `row '<id>': verdict field '<field>' diverged on both sides ...` | Two lanes recorded conflicting graded verdicts for the same matrix row (fail-closed, #4880) | Open the named matrix, pick the correct verdict for that row by hand, stage it, then `spec-kitty merge --resume` |
| `Merge failed. Resolve conflicts and try again.` | Git merge conflict occurred in a multi-workspace mission | Resolve conflicts, then `spec-kitty merge --resume` |
| `Merge failed. You may need to resolve conflicts.` | Git merge conflict occurred (legacy merge) | Resolve conflicts, then re-run merge |
| `Error: No merge state to resume` | No `.kittify/merge-state.json` exists | Run `spec-kitty merge --mission <slug>` to start a new merge |
| `⚠ Invalid merge state file cleared` | State file was corrupted | Start fresh with `spec-kitty merge` |
| `⚠ Git merge in progress - resolve conflicts first` | Unresolved conflict from previous attempt | Resolve conflicts, then `spec-kitty merge --resume` |
| `No merge state to abort` | No active merge to abort | Nothing to do, merge was already complete or never started |
| `Note: Rebase strategy not supported for execution-lanes.` | Used --strategy rebase with a multi-workspace mission | Use `merge` or `squash` strategy instead |
| `Pre-flight failed. Fix these issues before merging:` | One or more pre-flight checks failed | See numbered list below message, fix each issue |
| `Warning: No WP worktrees found for feature <slug>` | The mission may already be merged, not implemented yet, or still using only lane manifests without created worktrees | Check the mission slug, then create or inspect the expected execution workspaces |

---

## Command Reference

- [Merge Feature Guide](../missions/merge-mission.md) - Complete merge workflow
- [CLI Commands](../../../api/cli-commands.md) - Full CLI reference

## See Also

- [Merge a Feature](../missions/merge-mission.md) - Standard merge workflow
- [Accept and Merge](../missions/accept-and-merge.md) - Pre-merge validation
- [Handle Dependencies](../missions/handle-dependencies.md) - WP dependency management

## Background

- [Execution Lanes](../../../architecture/execution-lanes.md) - How worktrees and merging work
- [Git Worktrees](../../../architecture/git-worktrees.md) - Git worktree fundamentals

## Getting Started

- [Your First Mission](../../tutorials/your-first-mission.md) - Complete workflow walkthrough
