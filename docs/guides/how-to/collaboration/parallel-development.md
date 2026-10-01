---
title: How to Develop in Parallel with Multiple Agents
description: Run multiple Spec Kitty agents in parallel while keeping work packages isolated and coordinated.
doc_status: active
updated: '2026-06-14'
type: how-to
audience: docs/context/audience/external/tech-lead-evaluator.md
related:
- docs/guides/how-to/missions/handle-dependencies.md
- docs/guides/how-to/missions/implement-work-package.md
- docs/guides/how-to/collaboration/run-external-orchestrator.md
---
# How to Develop in Parallel with Multiple Agents

Parallel development lets you move independent work packages (WPs) at the same time while keeping each execution workspace isolated. Spec Kitty's lane-based worktree model makes this safe and predictable.

## Why Parallel Development?

- Shorten delivery time by running independent WPs concurrently.
- Keep changes isolated to avoid accidental cross-contamination.
- Use `spec-kitty agent tasks status` to coordinate and rebalance work.

## Prerequisites

- A feature with multiple WPs in `lane: "planned"`.
- Multiple terminals or agents available.
- Dependencies defined in WP frontmatter.

## Identifying Parallel Opportunities

1. List WPs and their dependencies.
2. Start WPs that do not depend on each other.
3. Hold any WP that depends on unfinished work.

## Example: Two Independent WPs

### Terminal 1 - Agent A

```bash
spec-kitty agent action implement WP01
cd <workspace path printed by the command>
# Agent A implements WP01
```

### Terminal 2 - Agent B (simultaneously)

```bash
spec-kitty agent action implement WP02
cd <workspace path printed by the command>
# Agent B implements WP02
```

## Example: Fan-Out Pattern

```
        WP01
      /  |  \
   WP02 WP03 WP04
```

Once WP01 is finished, three agents can work on WP02, WP03, and WP04 in parallel.

## Example: Dependent WPs

```bash
# Agent A completes WP01 first
spec-kitty agent action implement WP01
# ... implement and finish WP01

# Agent B starts WP02 after WP01 exists
spec-kitty agent action implement WP02 --agent <name>
cd <workspace path printed by the command>
```

## Best Practices

- Start with dependency-free WPs, then fan out.
- Communicate when base WPs complete so dependents can start.
- Keep each agent in its own resolved execution workspace path.
- Use workflow commands to keep lane history and status output accurate.

## Monitoring Parallel Work

In your terminal:

```bash
spec-kitty agent tasks status
```

Or in your agent:

```text
spec-kitty agent tasks status
```

Re-run it (or add `--json` for tooling) to follow lane movement as agents progress.

---

## Command Reference

- [Agent Subcommands](../../../api/agent-subcommands.md) - Workflow commands for agents
- [CLI Commands](../../../api/cli-commands.md) - Full CLI reference
- [Orchestrator API](../../../api/orchestrator-api.md) - Host contract for external automation providers

## See Also

- [Handle Dependencies](../missions/handle-dependencies.md) - Managing WP dependencies
- [Implement a work package](../missions/implement-work-package.md) - Starting a WP

## Background

- [Multi-Agent Orchestration](../../../architecture/multi-agent-orchestration.md) - Coordination patterns
- [Execution Workspace Model](../../../architecture/execution-lanes.md) - Isolation strategy
- [Git Worktrees](../../../architecture/git-worktrees.md) - How worktrees work

## Getting Started

- [Multi-Agent Workflow](../../tutorials/multi-agent-workflow.md) - Hands-on parallel tutorial
- [Run External Orchestrator](run-external-orchestrator.md) - Automate lane transitions with `spec-kitty-orchestrator`
