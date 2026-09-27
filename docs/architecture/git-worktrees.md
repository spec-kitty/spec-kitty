---
title: Git Worktrees Explained
description: "What git worktrees are and why Spec Kitty gives each execution lane its own: what worktrees share and keep separate, plus lifecycle commands and crash recovery."
doc_status: active
updated: '2026-09-26'
related:
- docs/architecture/branch-target-routing.md
- docs/architecture/execution-lanes.md
- docs/architecture/kanban-workflow.md
- docs/architecture/spec-driven-development.md
- docs/migrations/mission-id-canonical-identity.md
---
# Git Worktrees Explained

Git worktrees are the technology that enables Spec Kitty's parallel development model. This document explains what worktrees are, why Spec Kitty uses them, and how they work in the modern lane-based execution model.

> **Naming note:** a lane worktree path embeds `mid8` — the first 8 characters
> of the mission's ULID `mission_id`, as in `.worktrees/my-feature-01J6XW9K-lane-a/`
> — only when the recorded Mission slug itself embeds a mid8. Lane naming keys
> on the recorded Mission slug and lane id alone; the Mission identity is
> never an input to it (see ADR
> [`2026-09-26-2`](../adr/3.x/2026-09-26-2-lane-naming-keyed-on-creation-input.md)
> and [Execution Lanes §Naming](execution-lanes.md#naming)). The legacy
> numeric-prefix form `.worktrees/001-my-feature-lane-a/` shown in some
> examples below still resolves for pre-083 projects. See the
> [mission identity migration runbook](../migrations/mission-id-canonical-identity.md)
> for upgrade steps.

## What is a Git Worktree?

A git worktree is a linked working directory that lets you check out multiple branches simultaneously, each in its own directory. Unlike cloning a repository multiple times, all worktrees share the same `.git` directory and repository history.

**Normal git workflow** (one branch at a time):
```bash
# You can only have one branch checked out
git checkout feature-a
# To work on feature-b, you must switch branches
git checkout feature-b  # Now you're on feature-b, feature-a is gone
```

**With worktrees** (multiple branches simultaneously):
```bash
# Main repo stays on main branch
my-repo/               # main branch

# Each worktree has its own branch
.worktrees/feature-a/  # feature-a branch
.worktrees/feature-b/  # feature-b branch
```

You can now have three terminal windows open, each in a different directory, each on a different branch, all editing the same repository.

## Why Does Spec Kitty Use Worktrees?

### Parallel Development Without Branch Switching

Without worktrees, only one developer (or agent) can work at a time because git only allows one branch checked out per repository. With worktrees:

- Agent A works in `.worktrees/feature-lane-a/` on the WPs assigned to lane A
- Agent B works in `.worktrees/feature-lane-b/` on the WPs assigned to lane B
- Agent C works in `.worktrees/feature-lane-c/` on the WPs assigned to lane C

All three agents work simultaneously, each with their own files, their own uncommitted changes, and their own branch.

### Each Execution Lane Gets an Isolated Workspace

Problems with shared workspaces:
- Agent A edits `config.py`, breaks it
- Agent B (working on unrelated task) tries to run tests—they fail
- Both agents are now debugging each other's problems

With lane-based execution workspaces:
- Agent A's broken `config.py` only exists in lane A's workspace
- Agent B's workspace has clean files
- Isolation prevents cross-contamination

### Multiple Agents Can Work Simultaneously

Spec Kitty's parallel model requires:
1. Multiple independent branches
2. Multiple independent working directories
3. Shared repository history (for merging later)

Git worktrees provide all three.

## How Worktrees Work

### The .git Directory

When you clone a repository, git creates a `.git` directory containing:
- All commits
- All branches
- All tags
- Repository configuration

A worktree doesn't duplicate this. Instead, it creates a small file that points back to the main `.git` directory.

```
my-repo/
├── .git/                     # The real git database
├── src/                      # Your source files
├── .worktrees/
│   ├── feature-lane-a/
│   │   ├── .git              # Just a pointer file
│   │   └── src/              # Separate copy of source files
│   └── feature-lane-b/
│       ├── .git              # Just a pointer file
│       └── src/              # Another separate copy
```

### What Worktrees Share

All worktrees share:
- Commit history (all commits are in one place)
- Branch definitions (branches exist in main `.git`)
- Configuration (global git settings)
- Remote references (origin, upstream, etc.)

### What Worktrees Don't Share

Each worktree has its own:
- Working directory (files on disk)
- Index (staging area)
- Current HEAD (which commit is checked out)
- Uncommitted changes

This means Agent A can have uncommitted changes to `config.py` without affecting Agent B's `config.py`.

### Cross-Mission Concurrency Is a Different Question

Worktree isolation covers **lanes within one mission** — each lane worktree
has its own HEAD, index, and working directory, so parallel WPs in the same
mission cannot collide. It does **not** cover **two different missions
sharing the same primary checkout**. Mission-lifecycle commands (`mission
create`, status commits, `move-task`, backfill-topology) run against the
primary checkout's HEAD, branch, and index — the same ones every worktree's
`.git` file ultimately points back to — and there is no cross-mission lock
around those mutations. Two mission drivers issuing git operations from the
same primary checkout at the same time can interleave commits onto each
other's branch tips or strand commits on the wrong branch.

`mission create` also cannot be run from inside a worktree, so a second
concurrent mission cannot cleanly sidestep the primary checkout that way. If
you need two missions active at once, use a **separate clone** (its own
`.git`) for the second mission rather than assuming worktrees provide
enough isolation — worktree isolation is per-lane-within-a-mission, not
per-mission.

## Worktrees vs. Cloning

| Aspect | Worktree | Clone |
|--------|----------|-------|
| **Repository data** | Shared | Duplicated |
| **Disk space** | Minimal | Full copy |
| **Branches** | Shared | Independent |
| **Fetching/pushing** | Once for all | Once per clone |
| **Merging between** | Direct (same repo) | Requires remote |
| **Independence** | Partial | Complete |

**Use worktrees when**:
- Working on the same project
- Need to merge branches together later
- Want to minimize disk usage

**Use clones when**:
- Working on different projects
- Complete isolation is required
- May never merge together

## Git Commands for Worktrees

### List All Worktrees

```bash
git worktree list
```

Example output:
```
/path/to/my-repo               abc1234 [main]
/path/to/my-repo/.worktrees/feature-lane-a  def5678 [feature-lane-a]
/path/to/my-repo/.worktrees/feature-lane-b  ghi9012 [feature-lane-b]
```

### Create a New Worktree

```bash
# Create worktree with existing branch
git worktree add .worktrees/feature-lane-a feature-lane-a

# Create worktree and create new branch
git worktree add -b feature-lane-a .worktrees/feature-lane-a

# Create worktree from specific commit/branch
git worktree add -b feature-lane-b .worktrees/feature-lane-b feature-lane-a
```

### Remove a Worktree

```bash
# Clean removal (worktree must be clean)
git worktree remove .worktrees/feature-lane-a

# Force removal (discards uncommitted changes)
git worktree remove --force .worktrees/feature-lane-a
```

### Clean Up Stale Worktrees

```bash
# Prune worktrees whose directories no longer exist
git worktree prune
```

## Full Checkouts

Current Spec Kitty lane worktrees use full checkouts. Isolation is enforced by
lane computation, ownership metadata, workspace context, and merge guards
rather than by hiding files from the working directory.

That means an execution worktree still contains the full repository checkout,
but agents are expected to stay inside the files owned by the active WP and
lane.

## Common Issues

### "Worktree already exists"

**Error**:
```
fatal: 'feature-lane-a' already has a worktree at '.worktrees/feature-lane-a'
```

**Cause**: You're trying to create a worktree for a branch that's already checked out somewhere.

**Solution**:
```bash
# Find where it's checked out
git worktree list

# Either remove the existing worktree
git worktree remove .worktrees/feature-lane-a

# Or use that existing worktree instead
cd .worktrees/feature-lane-a
```

### "Branch is already checked out"

**Error**:
```
fatal: 'feature-lane-a' is already checked out at '/path/to/other/worktree'
```

**Cause**: Git won't let two worktrees have the same branch checked out.

**Solution**:
```bash
# Find the other worktree
git worktree list

# Remove it if not needed
git worktree remove /path/to/other/worktree

# Or work in the existing worktree
cd /path/to/other/worktree
```

### Cleanup After Crashes

If Spec Kitty or your system crashes mid-operation, worktrees may be left in an inconsistent state.

**Symptoms**:
- `git worktree list` shows non-existent directories
- Errors about locked worktrees
- Can't create new worktrees

**Solution**:
```bash
# Clean up stale worktree references
git worktree prune

# Force unlock if needed
git worktree unlock .worktrees/stuck-worktree

# Verify cleanup
git worktree list
```

### HEAD Detached in Worktree

**Symptom**: Commits in worktree aren't on any branch.

**Cause**: Worktree was created from a commit, not a branch.

**Solution**:
```bash
cd .worktrees/my-feature-01J6XW9K-lane-a
git checkout -b kitty/mission-my-feature-01J6XW9K-lane-a  # Create and switch to branch
```

## Further Reading

- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree) - Official git documentation

## See Also

- [Execution Lanes](execution-lanes.md) - How Spec Kitty uses worktrees
- [Branch-Target Routing](branch-target-routing.md) - Where each diff type lands (planning, status, code, docs) and the simple-case flat collapse when no lanes are configured
- [Spec-Driven Development](spec-driven-development.md) - The methodology that requires parallel work
- [Kanban Workflow](kanban-workflow.md) - How work progresses through lanes

---

*This document explains git worktrees for understanding. For practical steps in Spec Kitty, see the how-to guides.*

## Try It

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## How-To Guides

- [Upgrade to 0.11.0](../guides/how-to/installation/install-and-upgrade.md)
- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)

## Reference

- [File Structure](../api/file-structure.md)
- [CLI Commands](../api/cli-commands.md)
