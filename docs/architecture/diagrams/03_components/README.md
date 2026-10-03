---
title: Components (living)
description: 'Living components view (C4 level 3): current Spec Kitty internals and the planned charter service hexagon.'
doc_status: active
updated: '2026-10-03'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
---
# Components (living)

| Field | Value |
|---|---|
| Status | Living |
| Date | 2026-06-11 (charter service direction added 2026-10-03) |
| Scope | C4 Level 3 logical component view |
| Related ADRs | `2026-06-03-1`, `2026-06-03-2`, `2026-06-03-3`, `2026-06-07-1`, `2026-04-06-1`, `2026-05-16-1`, `2026-10-03-1` |

## Purpose

Define component-level boundaries for Spec Kitty while remaining
implementation-agnostic and behavior-focused, aligned to the four bounded
modules and the Op tier.

## Scope Rules

1. Focus on conceptual components and contracts, not file/class listings.
2. Explain behavior and interaction patterns that matter architecturally.
3. Keep component definitions aligned with the container boundaries and the ADRs.

## Component Diagram (Mermaid)

```mermaid
flowchart TB
    subgraph CLI["CLI Command Surface"]
      router["Command Router"]
      workflow["Workflow Command Set — specify/plan/tasks/implement/review/merge"]
      statusCmd["Status Mutation Command Set"]
      opCmd["Op Command Set — dispatch"]
    end

    subgraph Governance["Governance Module"]
      activation["Charter Activation Engine"]
      cascade["Charter Cascade (DRG-driven)"]
      orgExtends["Org Charter Extends Resolver"]
      doctrineCatalog["Doctrine Catalog Loader"]
      drg["Doctrine Relationship Graph"]
      profileRepo["Agent Profile Repository"]
      glossaryCorpus["Glossary Corpus"]
    end

    subgraph Mission["Mission Management Module"]
      missionLifecycle["Mission + WP Lifecycle"]
      lifecycleGateway["Lifecycle Command Gateway (status/ facade)"]
      reducer["Event Reducer + Snapshot Materializer"]
      eventStore["Append-only Event Store"]
      laneState["WP Lane State (State pattern)"]
    end

    subgraph Execution["Execution / Runtime Module"]
      resolveAction["resolve_action_context"]
      resolvePlacement["resolve_placement_only"]
      resolveSurface["resolve_status_surface_with_anchor"]
      fragments["Context Fragments — Identity/BranchRef/Workspace/StatusSurface/Placement/PromptSource"]
      workspaceCoord["Workspace + Worktree Coordinator"]
    end

    subgraph Kernel["Shared Kernel"]
      commitTarget["CommitTarget(ref, kind)"]
      guardEval["commit_guard.evaluate"]
      guardCap["GuardCapability"]
    end

    invocation["Op Invocation Context — open/close Op"]

    router --> workflow
    router --> statusCmd
    router --> opCmd

    opCmd --> invocation
    invocation --> activation
    activation --> cascade
    cascade --> drg
    activation --> doctrineCatalog
    drg --> profileRepo
    invocation --> missionLifecycle

    workflow --> missionLifecycle
    statusCmd --> lifecycleGateway
    missionLifecycle --> lifecycleGateway
    lifecycleGateway --> laneState
    laneState --> reducer
    reducer --> eventStore

    missionLifecycle --> resolveAction
    workflow -->|planning phase| resolvePlacement
    lifecycleGateway --> resolveSurface
    resolveAction --> fragments
    resolvePlacement --> fragments
    fragments --> workspaceCoord

    resolveAction --> commitTarget
    resolvePlacement --> commitTarget
    commitTarget --> guardEval
    guardCap --> guardEval
    guardEval -->|GuardVerdict| lifecycleGateway

    glossaryCorpus -. terminology guard .-> workflow
```

## Planned Charter Service Components

The planned service uses separate read and later write application modules over
one pure domain. Every infrastructure dependency points inward through a port.
The Python charter API seam remains outside this hexagon. See
[ADR 2026-10-03-1](../../../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md).

```mermaid
flowchart TB
    python["Python charter API seam — current external caller"]
    agent["Agent harness — planned MCP client"]

    subgraph Inbound["Inbound infrastructure"]
      rest["REST adapter — planned"]
      mcp["MCP adapter — planned"]
      writeApi["Write adapter — future"]
    end

    subgraph Application["Application"]
      readApp["Read application — planned"]
      writeApp["Write application — future"]
    end

    subgraph Domain["Pure charter domain"]
      models["Domain models"]
      policies["Validation, merge, activation, resolution policies"]
      ports["Repository ports"]
    end

    subgraph Outbound["Outbound infrastructure"]
      yaml["Lossless YAML adapter — future write path"]
      document["Document projection adapter — format deferred"]
      sql["SQL adapter — future and deferred"]
    end

    schemas[("Charter contract: contracts/charter/ and conformance fixtures")]

    python -.->|planned read delegation| rest
    python -.->|future migrated writes| writeApi
    agent -.->|planned governed read| mcp
    rest --> readApp
    mcp --> readApp
    writeApi -.-> writeApp
    readApp --> models
    readApp --> policies
    readApp --> ports
    writeApp -.-> models
    writeApp -.-> policies
    writeApp -.-> ports
    yaml -.-> ports
    document --> ports
    sql -.-> ports
    schemas -.->|constrains| rest
    schemas -.->|constrains| mcp
    schemas -.->|constrains| readApp
    schemas -.->|constrains| writeApp
    schemas -.->|constrains| yaml
```

Read and write applications do not depend on each other. Domain components
import no YAML, JSON, HTTP, MCP, database, or application-framework library.
The SQL adapter is a replaceable storage edge, not a domain or API change.
Direct MCP and Python-seam reads converge on the same read application.

## Component Responsibility Map

| Component | Module | Responsibility |
|---|---|---|
| Command Router | CLI | Normalizes and dispatches commands to the correct surface |
| Workflow Command Set | CLI | Drives specify/plan/tasks/implement/review/merge command families |
| Status Mutation Command Set | CLI | Handles lane-transition and status-mutation commands |
| Op Command Set | CLI | Handles `spec-kitty dispatch` governed invocations |
| Op Invocation Context | Op Tier | Opens an Op under resolved governance context and closes it with the real outcome |
| Charter Activation Engine | Governance | Plan/commit activation seam; writes config only after plan succeeds |
| Charter Cascade | Governance | Follows DRG `requires`/`suggests` edges for cascade (de)activation |
| Org Charter Extends Resolver | Governance | Canonical `org-charter.yaml extends:` chain resolver (`charter.org_extends`): base-first order, fail-closed on cycles/missing bases; the legacy loader delegates here |
| Doctrine Catalog Loader | Governance | Loads doctrine assets as typed artifacts; surfaces load diagnostics |
| Doctrine Relationship Graph | Governance | Generated edge graph; resolves profile lineage (`specializes_from`) |
| Agent Profile Repository | Governance | Resolves agent profiles via DRG traversal |
| Glossary Corpus | Governance | Canonical terminology surface and drift guard |
| Mission + WP Lifecycle | Mission Mgmt | Owns mission/WP lifecycle precedence and dependency gating |
| Lifecycle Command Gateway | Mission Mgmt | The `status/` OHS facade — normalizes lifecycle mutation requests |
| Event Reducer + Snapshot Materializer | Mission Mgmt | Deterministically reduces the event log to a snapshot |
| Append-only Event Store | Mission Mgmt | JSONL event I/O with corruption detection — sole lane authority |
| WP Lane State (State pattern) | Mission Mgmt | Models lane behavior per the State pattern (`2026-04-06-1`) |
| `resolve_action_context` | Execution | Resolves CWD-invariant `ExecutionContext` + single `CommitTarget` |
| `resolve_placement_only` | Execution | WP-less planning projection over the same resolution authority |
| `resolve_status_surface_with_anchor` | Execution | Single-pass status surface + primary anchor; fails closed |
| Context Fragments | Execution | Cohesive value-object fragments composed per operation (op-composite) |
| Workspace + Worktree Coordinator | Execution | Resolves/reuses the execution workspace |
| `CommitTarget(ref, kind)` | Shared Kernel | The one destination ref + topology kind for artifacts and status |
| `commit_guard.evaluate` | Shared Kernel | The ONE commit-protection decision (pure; echoes `target.ref`) |
| `GuardCapability` | Shared Kernel | Asserted-at-the-surface authorization parameter to `evaluate` |

## Canonical-shape notes

- Execution-state resolution lives in `mission_runtime`; consumers import only
  from the package root. The retired `core/execution_context.py` home is gone
  and is not depicted (`2026-04-25-1`, `2026-06-07-1`).
- `CommitTarget` is `(ref, kind)`, not `(worktree_root, destination_ref)` — see
  the 2026-06-10 addendum to ADR
  [`docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md`](../../../adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md).
- Authorization is one explicit `GuardCapability` argument; the five legacy
  privilege channels were folded in and are not depicted.

## Domain Alignment Matrix

| Domain (bounded module) | Primary Components |
|---|---|
| Governance | `Charter Activation Engine`, `Charter Cascade`, `Org Charter Extends Resolver`, `Doctrine Catalog Loader`, `Doctrine Relationship Graph`, `Agent Profile Repository`, `Glossary Corpus` |
| Mission Management | `Mission + WP Lifecycle`, `Lifecycle Command Gateway`, `Event Reducer + Snapshot Materializer`, `Append-only Event Store`, `WP Lane State` |
| Execution / Runtime | `resolve_action_context`, `resolve_placement_only`, `resolve_status_surface_with_anchor`, `Context Fragments`, `Workspace + Worktree Coordinator` |
| Shared Kernel | `CommitTarget(ref, kind)`, `commit_guard.evaluate`, `GuardCapability` |
| Op Tier (cross-module) | `Op Command Set`, `Op Invocation Context` |

## Behavioral Sequences

### Sequence A: Execution-state resolution (CWD-invariant)

```mermaid
sequenceDiagram
    participant User as Human/Agent
    participant Router as Command Router
    participant Mission as Mission + WP Lifecycle
    participant Runtime as resolve_action_context
    participant Kernel as CommitTarget(ref, kind)

    User->>Router: invoke a mission action
    Router->>Mission: dispatch lifecycle command
    Mission->>Runtime: resolve_action_context(repo_root, action, ...)
    Runtime->>Runtime: assemble fragments and resolve target_branch once
    Runtime->>Kernel: produce single CommitTarget
    Runtime-->>Mission: ExecutionContext + CommitTarget
```

### Sequence B: Lifecycle mutation and single-destination commit protection

```mermaid
sequenceDiagram
    participant User as Human/Agent
    participant Gateway as Lifecycle Command Gateway (status/)
    participant State as WP Lane State
    participant Reducer as Event Reducer
    participant Target as CommitTarget(ref, kind)
    participant Guard as commit_guard.evaluate

    User->>Gateway: request lifecycle transition
    Gateway->>State: validate guarded transition
    State->>Reducer: append event + materialize snapshot
    Gateway->>Target: take resolved destination
    Target->>Guard: evaluate(target, protection_state, capability)
    Guard-->>Gateway: GuardVerdict (resolved_destination echoes target.ref)
```

### Sequence C: Profile-governed Op invocation

```mermaid
sequenceDiagram
    participant User as Human/Agent
    participant OpCmd as Op Command Set
    participant Inv as Op Invocation Context
    participant Activation as Charter Activation Engine
    participant DRG as Doctrine Relationship Graph

    User->>OpCmd: spec-kitty dispatch
    OpCmd->>Inv: open Op
    Inv->>Activation: load action-scoped governance context
    Activation->>DRG: resolve active artifacts + profile lineage
    DRG-->>Inv: resolved governance context
    Inv-->>User: do the work under context, then close Op with outcome
```

### Sequence D: Charter activation and cascade

```mermaid
sequenceDiagram
    participant Human as Human In Charge
    participant Activation as Charter Activation Engine
    participant Cascade as Charter Cascade
    participant DRG as Doctrine Relationship Graph

    Human->>Activation: charter activate <kind> <artifact> --cascade
    Activation->>Activation: plan_activation (non-mutating validation)
    Activation->>Cascade: follow requires/suggests edges
    Cascade->>DRG: resolve cascade set (shared-reference safe)
    Activation-->>Human: commit_activation (writes config only after plan succeeds)
```

## Canonical work package FSM

```mermaid
stateDiagram-v2
    [*] --> planned
    planned --> claimed: claim (actor)
    claimed --> in_progress: start (workspace_context)
    in_progress --> for_review: ready_for_review (subtasks + evidence)
    for_review --> in_review: pick_up_review (reviewer)
    in_review --> approved: approve (review_ref)
    approved --> done: integrate (done evidence)

    in_review --> in_progress: changes_requested (review_ref)
    for_review --> in_progress: changes_requested (review_ref)

    planned --> blocked: blocked
    claimed --> blocked: blocked
    in_progress --> blocked: blocked
    for_review --> blocked: blocked
    in_review --> blocked: blocked
    approved --> blocked: blocked
    blocked --> in_progress: unblock

    planned --> canceled: cancel
    claimed --> canceled: cancel
    in_progress --> canceled: cancel
    for_review --> canceled: cancel
    in_review --> canceled: cancel
    approved --> canceled: cancel
    blocked --> canceled: cancel
```

Guard summary:

1. Canonical lanes: `planned`, `claimed`, `in_progress`, `for_review`,
   `in_review`, `approved`, `done`, `blocked`, `canceled`.
2. `done` and `canceled` are terminal unless an explicit force override is used.
3. `doing` is an input alias for `in_progress` and is never persisted.
4. Transition guards are transition-specific (actor, workspace context, review
   reference, done evidence, explicit reason fields).
5. Dependency gating: a WP cannot be claimed/implemented until every dependency
   is `approved` or `done`.

## Coupling and Trade-off Notes

1. A single execution-state surface (`mission_runtime`) trades a new top-level
   package for domain clarity and re-derivation prevention.
2. A single commit-protection decision (`commit_guard.evaluate`) makes
   authorization greppable and auditable for the LLM-agent threat model.
3. OHS facades keep `status` internals private to Mission Management.
4. Governance/doctrine coupling is deliberate to preserve policy traceability.

## Decision Traceability

<!-- DECISION: 2026-06-03-1 - Four bounded modules; status owned by Mission Management -->
<!-- DECISION: 2026-06-07-1 - mission_runtime canonical execution-state surface -->
<!-- DECISION: 2026-06-03-2 - CommitTarget(ref, kind) + GuardCapability single decision -->

## Traceability

- Domain model ADR: [`docs/adr/3.x/2026-06-03-1-execution-state-domain-model.md`](../../../adr/3.x/2026-06-03-1-execution-state-domain-model.md)
- Canonical execution surface ADR: [`docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md`](../../../adr/3.x/2026-06-07-1-execution-state-canonical-surface.md)
- ExecutionContext owner + CommitTarget ADR (incl. 2026-06-10 addendum): [`docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md`](../../../adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md)
- Effector/Actor model ADR: [`docs/adr/3.x/2026-06-03-3-effector-actor-model.md`](../../../adr/3.x/2026-06-03-3-effector-actor-model.md)
- WP State pattern ADR: [`docs/adr/3.x/2026-04-06-1-wp-state-pattern-for-lane-behavior.md`](../../../adr/3.x/2026-04-06-1-wp-state-pattern-for-lane-behavior.md)
- Doctrine-layer merge semantics ADR: [`docs/adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md`](../../../adr/3.x/2026-05-16-1-doctrine-layer-merge-semantics.md)
- Context view: [`../01_context/README.md`](../01_context/README.md)
- Container view: [`../02_containers/README.md`](../02_containers/README.md)
- Charter service strangler ADR: [`2026-10-03-1`](../../../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md)
