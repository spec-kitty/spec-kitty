---
title: Multi-Agent Parallel Development
description: 'Tutorial for Multi-Agent Parallel Development in Spec Kitty 3.2: Learn how to coordinate multiple AI agents working on different work packages simultaneously.'
doc_status: active
updated: '2026-08-11'
audience: docs/context/audience/external/project-owner.md
type: tutorial
related:
- docs/guides/tutorials/your-first-mission.md
---
# Multi-Agent Parallel Development

**Divio type**: Tutorial

Learn how to coordinate multiple AI agents working on different work packages simultaneously.

**Time**: ~1 hour
**Prerequisites**: Completed [Your First Mission](your-first-mission.md)

![Multi-agent parallel development - Mission Kitty splash](../../assets/images/multi-agent-workflow-mission-kitty.png)

_Stylized splash — the glowing parallel lanes are decorative. Worktrees, WP dependencies, and the hands-on steps are in the text below._

## Why Parallel Development?

- Shorter delivery time by splitting work packages
- Clear isolation with dedicated execution worktrees
- Reduced merge conflicts

## Understanding work package dependencies

Common dependency patterns:

- **Linear**: WP02 depends on WP01
- **Fan-out**: WP01 unblocks multiple packages
- **Diamond**: WP02 and WP03 depend on WP01, then WP04 depends on both

Dependencies are declared in each WP frontmatter.

## Hands-On: Two Agents, Two WPs

### Setup

Generate work packages for your feature.

In your agent:

```text
/spec-kitty.tasks
```

Confirm two independent packages are `lane: "planned"`.

### Terminal 1: Agent A on WP01

```bash
spec-kitty agent action implement WP01
cd <workspace path printed by the command>
# Agent A works here
```

### Terminal 2: Agent B on WP02

```bash
spec-kitty agent action implement WP02
cd <workspace path printed by the command>
# Agent B works here simultaneously
```

Each agent updates only their own worktree. Do not edit another agent's worktree.

## Handling Dependencies Through Execution Lanes

If WP02 depends on WP01, create WP02 from the WP01 base:

```bash
spec-kitty implement WP02
```

Expected output (abridged):

```
OK Created workspace: .worktrees/###-feature-lane-b
```

## Git Worktrees, Briefly

Each execution lane is a Git worktree on its own branch. Sequential WPs may reuse the same lane workspace, while independent WPs run in parallel in separate lane worktrees. For details, see [Execution Workspace Model](../../architecture/execution-lanes.md) and [Git Worktrees](../../architecture/git-worktrees.md).

## Tips for Coordinating Agents

- Run `spec-kitty agent tasks list-tasks` to see current lanes.
- Use `spec-kitty agent tasks add-history WP## --note "..."` to share progress.
- Avoid overlapping file edits across WPs.

## Troubleshooting

- **"lanes.json is required"**: Run task finalization before implementation.
- **Worktree already exists**: Run `git worktree list` and reuse the existing folder.
- **Agent edits the wrong WP**: Stop and switch to the workspace path printed for the correct WP before continuing.

## What's Next?

You've completed the core tutorials. Explore how-to guides for specific tasks or explanations for deeper understanding.

### Related How-To Guides

- [Parallel Development](../how-to/collaboration/parallel-development.md) - Run multiple agents simultaneously
- [Handle Dependencies](../how-to/missions/handle-dependencies.md) - Manage WP dependencies
- [Implement a work package](../how-to/missions/implement-work-package.md) - Detailed implementation steps

### Reference Documentation

- [Agent Subcommands](../../api/agent-subcommands.md) - Agent workflow commands
- [CLI Commands](../../api/cli-commands.md) - Full command reference
- [File Structure](../../api/file-structure.md) - Worktree layout

### Learn More

- [Multi-Agent Orchestration](../../architecture/multi-agent-orchestration.md) - Coordination patterns
- [Run External Orchestrator](../how-to/collaboration/run-external-orchestrator.md) - Automate WP execution with the external provider
- [Execution Workspace Model](../../architecture/execution-lanes.md) - Isolation strategy
- [Git Worktrees](../../architecture/git-worktrees.md) - How worktrees work
