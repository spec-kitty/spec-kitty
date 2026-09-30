---
title: Multi-Agent Orchestration
description: Coordination model for multi-agent delivery with a host-owned workflow state and external orchestration providers.
doc_status: active
updated: '2026-09-30'
audience: docs/context/audience/internal/lead-developer.md
related:
- docs/architecture/kanban-workflow.md
---
# Multi-Agent Orchestration

Spec Kitty supports multi-agent delivery through a host/provider split:

- `spec-kitty` owns workflow state, lane validation, and git-safe mutations.
- external providers such as `spec-kitty-orchestrator` run agents and call
  `spec-kitty orchestrator-api`.

This replaces in-core orchestration commands. The core CLI does not provide `spec-kitty orchestrate`.

## Why this model exists

1. Security boundary: autonomous orchestration is optional and can be disallowed by policy.
2. Extensibility: multiple provider strategies can exist without branching core CLI behavior.
3. Operational clarity: one host contract for state transitions and lifecycle events.
4. Review independence: one agent can implement while a different agent reviews
   without either agent owning the mission state machine.

## Core Principles

1. Planning in main, implementation in worktrees.
2. One worktree per WP.
3. Lane transitions validated by the host state model.
4. External providers drive automation through API calls, not direct file edits.
5. Activity logs and run state are audit artifacts, not the source of truth.

## Two orchestration styles

### 1) Manual (human- or agent-driven)

Manual coordination still works via normal commands:

```bash
spec-kitty next --agent <agent> --mission <slug>
# Your agent calls: spec-kitty agent action implement WP01 --agent <name>
spec-kitty agent tasks move-task WP01 --to for_review
spec-kitty agent tasks move-task WP01 --to done
```

### 2) External automated orchestration

Automated coordination is run by external providers such as `spec-kitty-orchestrator`.
Use a provider build that explicitly supports the current host API. The PyPI
`spec-kitty-orchestrator` `0.1.0` release appends `--json` to host API calls
and is not compatible with current hosts.

```bash
spec-kitty orchestrator-api contract-version
spec-kitty-orchestrator orchestrate --mission 034-my-feature --dry-run
spec-kitty-orchestrator orchestrate --mission 034-my-feature
```

Host-compatible provider loop responsibilities:

1. Discover ready WPs via host API.
2. Start implementation, prepare usable worktrees, and run agents there.
3. Transition WPs through review cycles.
4. Accept when WPs are accepted-ready (`approved` or `done`), then merge.

The common local pattern is:

```bash
spec-kitty-orchestrator orchestrate \
  --mission 034-my-feature \
  --impl-agent claude-code \
  --review-agent codex \
  --max-concurrent 1
```

That means Claude Code receives the WP prompt and writes the implementation;
Codex receives the same WP context after implementation and acts as reviewer.
The host, not either agent, decides which lane transitions are legal.

## Host API boundary

All state-changing automation calls flow through `spec-kitty orchestrator-api`.

- `start-implementation`
- `start-review`
- `transition`
- `append-history`
- `accept-mission`
- `merge-mission`

The host returns a stable JSON envelope with `success` and `error_code` for deterministic provider control flow.

The provider can be replaced. The boundary cannot. A custom orchestrator may
use a different scheduler, model router, queue, or CI runner, but it still must
call the same host API.

## Lane semantics

Public API lanes:

- `planned`
- `in_progress`
- `for_review`
- `in_review`
- `approved`
- `done`
- `blocked`
- `canceled`

Compatibility mapping:

- API `in_progress` maps to internal `doing`.
- `planned`, `for_review`, `in_review`, `approved`, and `done` map directly.

Current host review flow is:

```text
in_progress -> for_review -> in_review -> done
```

A rejected review moves back to implementation:

```text
in_review -> in_progress -> for_review
```

Providers should preserve a review reference for both approval and rejection so
humans can trace why a WP moved.

## Worktrees and Protected Branches

The orchestrator model assumes protected branches stay clean:

- mission planning artifacts live on the main project branch
- implementation runs in WP worktrees
- provider state lives under `.kittify/`
- host lane events are appended by the host API

This matters because activity-log updates may be committed by the host. A
provider that invokes mutation commands directly from protected `main` can hit
branch-protection errors. A compatible provider must create or reuse the
mission and WP worktrees before mutating state or spawning agents.

## Policy metadata and mutation authority

Run-affecting operations require policy metadata (`--policy`) and are validated by the host.

This ensures:

- identity and mode are explicit for each mutation
- malformed or secret-like policy payloads are rejected
- orchestrators cannot bypass host transition rules

## What this means for teams

- Teams that want full automation can run an external provider.
- Teams with strict security constraints can keep orchestration manual.
- Teams can build custom providers while preserving a consistent workflow model.
- Teams can test automation safely with deterministic fake-agent e2e before
  enabling real agent CLIs on a trusted machine.

## See Also

- [Orchestrator Quickstart](../guides/tutorials/orchestrator-quickstart.md)
- [Run the External Orchestrator](../guides/how-to/collaboration/run-external-orchestrator.md)
- [Build a Custom Orchestrator](../guides/how-to/collaboration/build-custom-orchestrator.md)
- [Orchestrator API Reference](../api/orchestrator-api.md)
- [Kanban Workflow](kanban-workflow.md)
