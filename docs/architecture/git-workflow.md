---
title: 'Git Workflow: Who Does What'
description: "The boundary between infrastructure git that Python owns (worktrees, status commits, merges) and content git that agents own (code, rebases, conflicts), plus auto-commit rules."
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/execution-lanes.md
- docs/architecture/git-worktrees.md
---
# Git Workflow: Who Does What

Spec Kitty draws a hard line between **infrastructure git** and **content git**. Python handles all the plumbing -- resolving execution workspaces, creating worktrees, committing status changes, merging branches, cleaning up. Agents (and humans) handle all the content -- writing code, committing implementations, rebasing, and resolving conflicts.

Understanding this boundary matters because crossing it causes breakage. An agent that creates a worktree manually will end up without workspace context, without canonical lane assignment, and without proper branch naming. A human who commits planning artifacts from inside a worktree will pollute the wrong branch.

> **Companion doc:** [Git Worktrees](git-worktrees.md) explains the underlying git worktree technology. This document explains how Spec Kitty uses that technology in practice.

## The Responsibility Boundary

| Git Operation | Who | When |
|---|---|---|
| `git worktree add` | Python | `spec-kitty agent action implement WP## --agent <name>` |
| `git commit` (planning artifacts) | Python | Before worktree creation |
| `git commit` (lane transitions) | Python | WP moves to doing / for_review |
| `git commit` (implementation code) | **Agent** | After writing code in worktree |
| `git rebase` (stale lane sync) | **Agent** | When the mission branch advanced and the lane must resync |
| `git merge` (lane into mission, mission into target) | Python | `spec-kitty consolidate` |
| `git push` | Python (opt-in) | `spec-kitty consolidate --push` only |
| `git push` | **Agent** | Any other push scenario |
| Conflict resolution | **Agent** | During rebase or manual merge |
| `git worktree remove` | Python | After successful consolidation |
| `git branch -d` (cleanup) | Python | After successful consolidation |

The pattern is straightforward: Python owns the lifecycle scaffolding. Agents own the work that happens inside that scaffolding.

## Worktree Lifecycle

Every execution workspace passes through five stages.

### 1. Created

```bash
spec-kitty agent action implement WP01 --agent <name>
```

Python resolves the canonical workspace for the WP, runs `git worktree add` if needed, creates a workspace context file at `.kittify/workspaces/<mission>-<workspace>.json`, and sets the WP status to `in_progress`.

For dependent WPs, rely on task finalization to place the work in the correct execution lane:

```bash
spec-kitty agent action implement WP02 --agent <name>
```

If WP01 and WP02 share a lane, the same workspace is reused sequentially. If they do not share a lane, each lane branches from the mission branch and integrates through the lane-only consolidation flow.

### 2. Active

The agent works inside the worktree directory:

```bash
cd .worktrees/042-feature-lane-a
# Write code, run tests, iterate
git add src/ tests/
git commit -m "feat(WP01): implement auth middleware"
```

The WP status is `in_progress`. All implementation commits are the agent's responsibility -- Python never commits code.

### 3. For Review

```bash
spec-kitty agent tasks move-task WP01 --to for_review --note "Ready for review"
```

Python auto-commits the WP frontmatter change to record the lane transition. Before accepting the transition, it validates that the worktree has at least one commit ahead of the base branch. If there are zero implementation commits, the transition is rejected.

### 4. Consolidated

```bash
spec-kitty accept --mission 042-feature
spec-kitty consolidate --mission 042-feature
```

Acceptance validates that all WPs are approved or done before consolidation. Python
then lands the lane branches onto the local target branch in dependency order (in
lane mode, lanes land on the mission branch first, then the mission branch lands on
the target).

1. **Land the work.** The default strategy is **squash**; `--strategy merge` and
   `--strategy rebase` are the alternatives. The chosen strategy is persisted in
   `ConsolidationState.strategy`, so `consolidate --resume` keeps it.
2. **Verify the landing.** A reconciliation gate checks that every content change on the
   target can be attributed to an approved WP, and that every approved WP's own change is
   present on the target. If it fails or refuses, the target is restored to its pre-run tip
   with a compare-and-swap rollback.
3. **Clean up.** Lane worktrees are removed (`git worktree remove`) and lane branches
   deleted, unless `--keep-worktree` / `--keep-branch` or the mission's
   `retain_worktrees` / `retain_branches` metadata says to keep them.

Consolidation is local only; publish the result through a topic branch and a pull
request. See [status model](status-model.md) and the `spec-kitty consolidate` help for
the details, and the
[CLI reference](../api/cli-commands.md#spec-kitty-consolidate-exit-codes-and-refusal-codes)
for its exit codes and refusal codes.

### 5. Cleaned Up

After consolidation (unless retention was requested), the worktree directory is gone, the branch is deleted, and the workspace context file is removed. The WP's work now lives on the target branch.

## Auto-Commit Behavior

Spec Kitty auto-commits in two situations. Both are controlled by the `auto_commit` setting.

### Planning Artifact Commits

Before creating a worktree, Python checks whether `kitty-specs/<mission>/` has uncommitted changes on the primary branch. If so, it commits them automatically:

```
chore: Planning artifacts for 042-feature
```

This ensures planning work is preserved before the worktree branches off.

### Lane Transition Commits

When a WP moves to `doing` or `for_review`, Python uses the **safe-commit pattern**:

1. Stash the current staging area
2. Stage only the target files (WP frontmatter, status artifacts)
3. Commit with a message like `chore: Start WP01 review [claude]`
4. Pop the stash to restore previous staging

This prevents accidentally committing agent work-in-progress alongside the lane change.

### Status Events Are Not Auto-Committed

`emit_status_transition()` updates the event log (`status.events.jsonl`) and snapshot (`status.json`), but does not commit these files. They accumulate as uncommitted changes until the next lane transition or the agent's next commit. This is intentional -- status events happen frequently, and committing each one individually would create excessive git noise.

### Configuration

```yaml
# .kittify/config.yaml
auto_commit: true    # default
```

When `false`, agents must commit everything manually, including planning artifacts and lane transitions.

Per-command override: `--no-auto-commit` on `spec-kitty implement`.

## What Agents Must Do Manually

These operations are never automated. Each requires judgment that Python cannot provide.

### Implementation Commits

All code, tests, and configuration changes must be committed by the agent:

```bash
cd <workspace path printed by spec-kitty implement>
git add src/ tests/
git commit -m "feat(WP01): implement auth middleware"
```

There is no auto-save, no auto-commit of code. If the agent does not commit, the work is lost when the worktree is removed.

### Rebasing Dependent WPs

When WP02 depends on WP01 and WP01 receives new commits after WP02 branched:

```bash
cd <workspace path printed by spec-kitty implement>
git rebase <base branch printed by spec-kitty>
# Resolve conflicts if any
git add .
git rebase --continue
```

Spec Kitty displays a warning when it detects the base has diverged, but it does not perform the rebase. The agent must handle this.

### Multi-Parent Dependencies

Git can only branch from one parent. If WP04 depends on both WP02 and WP03:

```bash
spec-kitty agent action implement WP04 --agent <name>
```

Task finalization resolves multi-dependency lane ownership before implementation starts.

### Pushing

`spec-kitty consolidate --push` is the only automated push. All other push operations are the agent's responsibility. Never push unprompted.

### Conflict Resolution

If `spec-kitty consolidate` encounters conflicts, it stops and reports the conflicting files. The agent must resolve them manually, then complete the consolidation. Python does not attempt auto-resolution.

## Anti-Patterns

### Creating Worktrees Manually

```bash
# WRONG: Manual worktree creation
git worktree add -b my-branch .worktrees/my-branch main
```

Manual worktrees lack workspace context (`.kittify/workspaces/*.json`), lane metadata, and canonical branch naming. Spec Kitty commands will not recognize them reliably.

Always use `spec-kitty implement`.

### Committing in the repository root checkout during implementation

```bash
# WRONG: Committing code in the repository root checkout
cd my-repo/
git add src/new-feature.py
git commit -m "feat: new feature"
```

The repository root checkout is for planning artifacts only. Implementation commits belong in the worktree. Committing code in the repository root checkout will create merge conflicts when the worktree branches are merged back.

### Pushing Without Being Asked

```bash
# WRONG: Auto-pushing
git push origin <resolved workspace branch>
```

Never push unless the user explicitly requests it or you are using `spec-kitty consolidate --push`. Unexpected pushes can trigger CI pipelines, interfere with other agents, and make rollbacks difficult.

### Modifying Other WPs From a Worktree

Each worktree is isolated to one work package. Editing files that "belong" to another WP creates merge conflicts when both WPs merge. Stay within your WP's scope.

### Skipping Commits Before Review

```bash
# WRONG: Moving to review without committing
spec-kitty agent tasks move-task WP01 --to for_review
# Error: WP01 has 0 commits ahead of base
```

Spec Kitty validates that the worktree has implementation commits before allowing the transition to `for_review`. Commit your work first.

## No Git Hooks

Spec Kitty does not install or manage git hooks. The pre-commit hook that previously handled UTF-8 encoding validation was replaced with a Python text sanitization layer. There are no `.git/hooks/` files to worry about.

---

*This document explains the git workflow boundary. For the underlying worktree technology, see [Git Worktrees](git-worktrees.md). For the execution workspace model, see [Execution Workspace Model](execution-lanes.md).*

## Try It

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)

## Reference

- [CLI Commands](../api/cli-commands.md)
- [File Structure](../api/file-structure.md)
