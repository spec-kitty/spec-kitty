---
title: Explanation
description: 'Understanding-oriented background on Spec Kitty: spec-driven development, the mission system, execution lanes, git workflow, and multi-agent orchestration.'
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/ai-agent-architecture.md
- docs/architecture/execution-lanes.md
- docs/architecture/git-workflow.md
- docs/architecture/git-worktrees.md
- docs/architecture/kanban-workflow.md
- docs/architecture/mission-system.md
- docs/architecture/mission-type-resolution.md
- docs/architecture/multi-agent-orchestration.md
- docs/architecture/runtime-loop.md
- docs/architecture/spec-driven-development.md
---
# Explanation

Understanding-oriented pages that explain *why* Spec Kitty works the way it does. Start
here when you want the mental model behind a capability rather than step-by-step instructions.

## Key pages

- [Spec-driven development](spec-driven-development.md) — the core methodology.
- [Mission system](mission-system.md) — how missions and work packages relate.
- [Mission-type resolution](mission-type-resolution.md) — the doctrine → charter → core seam that resolves per-mission-type behaviour.
- [Execution lanes](execution-lanes.md) and [git worktrees](git-worktrees.md) — the parallel execution model.
- [Git workflow](git-workflow.md) — what git operations the runtime owns versus the agent.
- [Multi-agent orchestration](multi-agent-orchestration.md) — coordinating work across agents.
- [Kanban workflow](kanban-workflow.md) and [runtime loop](runtime-loop.md) — the mission control loop.
- [AI agent architecture](ai-agent-architecture.md) — how supported agents integrate.
- [Doctrine artifact kinds](doctrine-kinds.md) — what each of the eight doctrine artifact kinds is for.
- [SPDD and the REASONS Canvas](spdd-reasons.md) — the opt-in structured-prompt-driven-development doctrine pack.
- [Status model](status-model.md) and [mission transition gates](mission-gates.md) — how lane state is recorded and guarded.
- [Post-merge partition authority](post-merge-partition-authority.md) — which bytes win after consolidation, and which surface readers trust.

The full list is in the [architecture index](index.md).

## See also

- [Tutorials](../guides/tutorials/index.md) — learning-oriented walkthroughs.
- [How-to guides](../guides/index.md) — task-oriented instructions.
- [Reference](../api/index.md) — authoritative specifications.
