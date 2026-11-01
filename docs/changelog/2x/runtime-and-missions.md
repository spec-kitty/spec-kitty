---
title: 2.x Runtime, Mission Types, and Missions
description: Historical Spec Kitty 2.x archive page for 2.x Runtime, Mission Types, and Missions; use Spec Kitty 3.2 docs for current Charter-era workflows.
doc_status: deprecated
updated: '2026-06-03'
related:
- context
- changelog/2x/orchestration-and-api
---
> Archive notice: This page documents historical Spec Kitty behavior and is not the current 3.2 workflow. Start with [Spec Kitty 3.2](../../context/index.md) for current docs.

# 2.x Runtime, Mission Types, and Missions

Spec Kitty's mission system lets you choose a workflow blueprint optimized for your type of work. Each mission type defines the phases, required artifacts, validation guards, and agent context for a specific work type. You select a mission type when creating a mission, and it governs that mission for its entire lifecycle.

Terminology note:
- `Mission Type` = reusable workflow blueprint
- `Mission` = concrete tracked item in `kitty-specs/<mission-slug>/`
- `Mission Run` = runtime/session instance
- `Feature` = compatibility alias for a software-dev mission

The runtime is the engine that drives mission execution. It resolves which mission-type assets to load, determines what the next action should be, and enforces guard conditions before transitions.

## The 4 Built-In Mission Types

| Mission | Purpose | Key Phases | Default? |
|---------|---------|------------|----------|
| **software-dev** | Full development lifecycle | specify, plan, tasks, implement, review, accept | Yes |
| **research** | Systematic evidence-gated investigation | scoping, methodology, gathering, synthesis, output | No |
| **plan** | Goal-oriented strategic planning | discovery, specify, plan, refine | No |
| **documentation** | Divio-based documentation creation | specify, plan, audit, create, validate | No |

Each mission type defines its own step DAG (directed acyclic graph of actions), its own required artifacts, and its own guard conditions for action transitions.

## Mission-Type Assets

Packaged mission defaults for 2.x live under doctrine:

1. `src/doctrine/missions/software-dev/` -- software development workflow
2. `src/doctrine/missions/plan/` -- planning workflow
3. `src/doctrine/missions/research/` -- research workflow
4. `src/doctrine/missions/documentation/` -- documentation workflow

Each mission-type directory contains a `mission-runtime.yaml` (step DAG, guards, artifacts) and a set of command templates that are deployed to agent directories.

## The Hierarchy: Mission Type, Mission, work package, Execution Workspace

Understanding how the pieces nest is key to understanding Spec Kitty:

```
Mission Type (reusable workflow blueprint, e.g. software-dev)
  |
  +-- Mission (concrete tracked item, in kitty-specs/###-name/)
        |
        +-- Work Package (one parallelizable slice, tasks/WP01.md)
              |
              +-- Execution Workspace (isolated git worktree, usually .worktrees/###-name-lane-a/)
```

- **Mission Type** -- selected when the mission is created; determines actions, artifacts, and guards.
- **Mission** -- stored in `kitty-specs/###-name/`; linked to its mission type via `meta.json`.
- **Feature** -- legacy software-dev alias for a mission.
- **work package** -- one unit of implementable work; has its own status on the kanban board and its own dependencies.
- **Execution Workspace** -- the git worktree resolved for implementation. The runtime creates exactly one worktree per execution lane, and sequential WPs in the same lane reuse that worktree.

Different missions in the same project can use different mission types simultaneously.

## Canonical Agent Loop: `spec-kitty next`

2.x treats `spec-kitty next --agent <name>` as the canonical loop entrypoint for agent execution. The command inspects the current mission's action state and WP statuses, then returns exactly one actionable instruction: which mission action to advance, which WP to implement, or what is blocking progress.

The loop works with two orthogonal state machines:

- **Mission action state** -- which outer lifecycle action are we in? (`specify`, `plan`, `implement`, ...)
- **WP status** -- where is each work package in its lifecycle? (planned, claimed, in_progress, for_review, in_review, approved, done)

Together they determine the next action. For example: "We are in the implement phase, WP01 is approved, WP02 is in_progress, WP03 is planned -- your next action is implement WP03."

Agents call `spec-kitty next` in a loop, executing whatever it returns until the mission is complete. This keeps agent behavior deterministic and auditable -- the runtime decides what happens next, not the agent.

ADR reference: `docs/adr/2.x/2026-02-17-1-canonical-next-command-runtime-loop.md`

## Mission Discovery and Loading

Mission-type discovery and loading are runtime-owned and resolved through explicit precedence rather than duplicated ad-hoc loaders.

The resolution order is:

1. Project override (`.kittify/missions/<name>/`)
2. Project legacy location
3. User-global mission-specific location (`~/.spec-kitty/missions/<name>/`)
4. User-global location (`~/.spec-kitty/`)
5. Packaged doctrine mission defaults

ADR reference: `docs/adr/2.x/2026-02-17-2-runtime-owned-mission-discovery-loading.md`

Implementation references:

1. `src/specify_cli/runtime/home.py`
2. `src/specify_cli/runtime/resolver.py`

## Status and Event Model

2.x status behavior is event-driven with canonical transition semantics and reducer materialization. Every lane transition is an immutable event appended to `status.events.jsonl`. The reducer deterministically produces a snapshot from the event log.

The 9-lane state machine:

```
planned --> claimed --> in_progress --> for_review --> in_review --> approved --> done
```

Plus `blocked` (reachable from planned/claimed/in_progress/for_review/in_review/approved) and `canceled` (reachable from all non-terminal lanes). Alias: `doing` → `in_progress`.

ADR references:

1. `docs/adr/2.x/2026-02-09-1-canonical-wp-status-model.md`
2. `docs/adr/2.x/2026-02-09-2-wp-lifecycle-state-machine.md`
3. `docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md`
4. `docs/adr/2.x/2026-02-09-4-cross-repo-evidence-completion.md`

## External Orchestration Boundary

2.x orchestration automation is externalized behind `spec-kitty orchestrator-api`.

1. Host state and transition rules remain in `spec-kitty`.
2. External providers (for example `spec-kitty-orchestrator`) call the host API contract.
3. Provider implementations should not directly mutate lane/frontmatter state files.

See [Orchestration and API Boundary](orchestration-and-api.md) for operator and provider guidance.

---

## Learn More

- **Deep dive on missions**: [The Mission System Explained](../../architecture/mission-system.md) -- why missions exist, how they shape your experience, detailed comparison of all four built-in missions
- **Kanban workflow**: [Kanban Workflow Explained](../../architecture/kanban-workflow.md) -- how lanes work and what happens when work moves between them
- **Workspace model**: [Execution Workspace Model](../../architecture/execution-lanes.md) -- lane-based worktrees only
- **CLI reference**: [CLI Commands Reference](../../api/cli-commands.md) -- complete `next`, `mission`, and `status` subcommand details
