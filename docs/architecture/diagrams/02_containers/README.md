---
title: Containers (living)
description: 'Living containers view (C4 level 2): current logical containers and the planned charter read-service transition.'
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/runtime-execution-domain.md
- docs/architecture/diagrams/03_components/README.md
---
# Containers (living)

| Field | Value |
|---|---|
| Status | Living |
| Date | 2026-06-11 (charter service direction added 2026-10-03) |
| Scope | C4 Level 2 container model — four bounded modules + Op tier |
| Related ADRs | `2026-06-03-1`, `2026-06-03-2`, `2026-06-03-3`, `2026-06-07-1`, `2026-04-25-1`, `2026-05-16-1`, `2026-10-03-1` |

## Purpose

Show the major logical containers in Spec Kitty and define how they
collaborate to enforce governance, mission lifecycle, execution-state
resolution, and the single commit-protection decision.

## Scope Rules

1. Use stable logical container boundaries (the four bounded modules), not
   implementation package inventories.
2. Focus on contracts, responsibilities, and behavior loops.
3. Defer intra-module component detail to [`../03_components/README.md`](../03_components/README.md).
4. Use [`runtime-execution-domain.md`](runtime-execution-domain.md) for the
   deeper lifecycle/routing/FSM detail that would overload the top-level map.

## Container Diagram (Mermaid)

The four bounded modules are the top-level containers. They communicate through
**Open Host Service (OHS) facades** only
([`docs/adr/3.x/2026-06-03-1-execution-state-domain-model.md`](../../../adr/3.x/2026-06-03-1-execution-state-domain-model.md)).

```mermaid
flowchart TB
    cli["CLI Command Surface"]

    subgraph Governance["Governance Module"]
      charter["Charter Engine — activation, cascade, extends"]
      doctrine["Charter Offering + DRG"]
      glossary["Glossary Corpus"]
    end

    subgraph Mission["Mission Management Module"]
      missionLifecycle["Mission + WP lifecycle"]
      statusFacade["status/ OHS facade — sole status authority"]
      planning["Planning artifacts (specify/plan/tasks)"]
    end

    subgraph Execution["Execution / Runtime Module"]
      missionRuntime["mission_runtime — canonical execution surface"]
      placement["resolve_placement_only — planning CommitTarget"]
      surface["resolve_status_surface_with_anchor — status surface"]
      workspace["Workspace + worktree lifecycle"]
    end

    subgraph Kernel["Shared Kernel"]
      commitTarget["CommitTarget(ref, kind)"]
      commitGuard["commit_guard.evaluate + GuardCapability"]
    end

    op["Op Tier — dispatch + pre/post-mission lifecycle"]
    orchestrator["External Orchestrator"] --> cli
    moments["Zeitgeist moment publisher — status/zeitgeist_bridge + zeitgeist_client"]
    relay["Team's Zeitgeist relay (external)"]
    extTracker["External Tracker (local provider or via Team Kitty)"]

    cli --> op
    op -->|action-scoped context| charter
    charter --> doctrine
    charter --> glossary
    op --> missionLifecycle

    cli --> missionLifecycle
    missionLifecycle --> statusFacade
    missionLifecycle --> planning
    statusFacade -->|after local persistence, when drain is on| moments
    moments -->|one bounded moment, no queue, no retry| relay
    cli -->|tracker commands| extTracker

    missionLifecycle -->|resolve_action_context| missionRuntime
    planning -->|resolve_placement_only| placement
    statusFacade -->|resolve_status_surface_with_anchor| surface
    placement --> missionRuntime
    surface --> missionRuntime
    missionRuntime --> workspace

    missionRuntime -->|produces| commitTarget
    placement -->|produces| commitTarget
    commitTarget --> commitGuard
    commitGuard -->|GuardVerdict on resolved ref| missionLifecycle
```

## Planned Charter Service Containers

This refinement marks planned and future elements explicitly. It does not claim
that a Java service directory or release artifact exists. See
[ADR 2026-10-03-1](../../../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md).

```mermaid
flowchart LR
    agent["Agent harness"]

    subgraph Python["Spec Kitty CLI (specify_cli) — current"]
      callers["CLI, runtime, and glossary callers — import charter internals directly"]
      writer["Current Python write paths — activation commit_plan, charter_yaml_io, compile"]
      lifecycle["Service launch and lifecycle — planned"]
    end

    subgraph Planned["Charter layer (src/charter) — planned"]
      seam["Charter API seam — planned (#645): transport client only"]
    end

    subgraph Java["Charter Service — planned, per worktree (Java 25, Spring Boot 4)"]
      readApi["REST and MCP read adapters — planned"]
      reader["Java charter read application — planned"]
      javaWriter["Java write application — future"]
      projection["Document projection — format deferred"]
    end

    contract[("Charter contract: contracts/charter/ and conformance corpus")]
    yaml[("Authored charter and pack YAML")]
    status["Mission Status Read service — separate sibling"]

    agent -->|CLI| callers
    callers -.->|planned: move onto the seam| seam
    agent -.->|planned governed MCP read| readApi
    callers -->|current write operations| writer
    seam -.->|planned: writes stay in Python| writer
    writer --> yaml
    lifecycle -.->|planned: starts service, gives seam endpoint| seam
    lifecycle -.->|planned: launches and stops| Java
    seam -.->|planned production reads| readApi
    seam -.->|future migrated writes| javaWriter
    readApi --> reader
    reader -->|authored source| yaml
    reader -->|derived read model| projection
    javaWriter -.->|later, operation by operation| yaml
    contract -.->|constrains| seam
    contract -.->|constrains| reader
    contract -.->|constrains| javaWriter
    status ~~~ Java
```

The seam is code under `src/charter/` and holds only a transport client. Service launch and
lifecycle live in `specify_cli`, so `charter` gains no outbound edge to `specify_cli`.
The document projection is an implementation detail and not the rejected design where
Java only serves a permanent Python-compiled projection. The Mission Status Read
service shares neither charter domain nor process. Direct MCP and Python-seam
reads enter the same application and domain policies.

## Container Responsibilities

| Container | Core Responsibility | Behavioral Ownership |
|---|---|---|
| CLI Command Surface | Interactive and scripted command entry point | Validates command intent and routes to the Op tier and bounded modules |
| Op Tier | Standalone dispatch invocations and the pre/post-mission lifecycle | Opens an Op under resolved governance context, does the work, closes the Op with the real outcome |
| Charter Engine | Charter interview, activation, cascade, and `org-charter.yaml` `extends:` resolution | Produces governance constraints (the active charter/doctrine policy) consumed by the Op tier and missions |
| Charter Offering + DRG | Typed governance/mission assets and the Doctrine Relationship Graph | Loads/validates doctrine resources; resolves profile lineage via DRG edges |
| Glossary Corpus | Canonical terminology surface | Supplies terms and guards terminology drift |
| Mission + WP lifecycle | Mission and work-package lifecycle precedence | Owns lifecycle sequencing; delegates execution-state resolution to `mission_runtime` |
| `status/` OHS facade | Canonical lifecycle and event semantics | **Sole** status authority — no module outside Mission Management imports `status` internals |
| Planning artifacts | specify / plan / tasks / finalize-tasks outputs | Commits planning artifacts to the resolved `CommitTarget` |
| `mission_runtime` | Canonical execution-state surface | Resolves CWD-invariant `ExecutionContext` and the single `CommitTarget`; consumers import only from the package root |
| `resolve_placement_only` | WP-less planning-phase projection | One narrow entry point over the same resolution authority — the planning `CommitTarget` |
| `resolve_status_surface_with_anchor` | Single-pass status-surface + primary-anchor resolution | The one status-surface authority; fails closed rather than handing back a primary surface (kills the split-brain class) |
| `CommitTarget(ref, kind)` | The one ref artifacts and status events resolve to | Self-validating value object pairing the destination `ref` with its topology `kind` |
| `commit_guard.evaluate` + `GuardCapability` | The ONE commit-protection decision | Pure function: echoes `CommitTarget.ref` as the resolved destination; capability is asserted at the call site, never derived |
| Zeitgeist moment publisher | Publishes a lane-transition moment to the team's relay | Runs only after the event is persisted locally and only when drain is on; fails open on availability, closed on identity ([Team Kitty and Zeitgeist](../../../context/team-kitty.md)) |

## Canonical-shape notes (what these containers are NOT)

- The execution-state surface is the top-level `mission_runtime` package. The
  retired `specify_cli/core/execution_context.py` home is **gone** and is
  deliberately not depicted (`2026-04-25-1`, `2026-06-07-1`).
- `CommitTarget` is `(ref, kind)` — a destination ref paired with its topology
  classification. The earlier sketch of `(worktree_root, destination_ref)` is
  superseded and **not** depicted (see the 2026-06-10 addendum to
  [`docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md`](../../../adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md)).
- Commit protection is one pure decision (`commit_guard.evaluate`) parameterized
  by an explicit `GuardCapability`; the five legacy privilege channels were
  folded into that capability and are not depicted.
- The retired sync transport (daemon, offline queue, batch ingress) is gone and
  is not depicted; the only hosted outbound path is the Zeitgeist moment.

## Domain-to-Container Allocation

| Domain (bounded module) | Primary Containers | Secondary Containers |
|---|---|---|
| Governance | Charter Engine, Charter Offering + DRG, Glossary Corpus | CLI Command Surface, Op Tier |
| Mission Management | Mission + WP lifecycle, `status/` OHS facade, Planning artifacts | CLI Command Surface, Zeitgeist moment publisher |
| Execution / Runtime | `mission_runtime`, `resolve_placement_only`, `resolve_status_surface_with_anchor`, Workspace lifecycle | Mission + WP lifecycle |
| Shared Kernel | `CommitTarget(ref, kind)`, `commit_guard.evaluate` + `GuardCapability` | — |
| Op Tier (cross-module) | Op Tier | Charter Engine, Mission + WP lifecycle |

## Behavioral Collaboration Loops

### Loop A: Mission lifecycle and execution-state resolution

1. CLI captures the command and routes it to the Op tier / Mission Management.
2. Mission Management calls `resolve_action_context` on `mission_runtime` to get
   a CWD-invariant `ExecutionContext` and the single `CommitTarget`.
3. Lifecycle mutation commands execute through the `status/` OHS facade.
4. The facade validates transitions, appends events, and materializes snapshots.

### Loop B: Single-destination commit protection

1. `mission_runtime` (or the planning-phase `resolve_placement_only`) produces
   one `CommitTarget(ref, kind)`.
2. `commit_guard.evaluate` decides — purely, from the target plus an asserted
   `GuardCapability` — whether the commit may land on that ref.
3. The verdict echoes `CommitTarget.ref` as the resolved destination; the guard
   never re-derives a destination and never performs a push.

### Loop C: Governance-context-scoped Ops

1. The Op tier asks the Charter Engine for the action-scoped governance context.
2. The Charter Engine resolves the active charter/doctrine (including
   `org-charter.yaml` `extends:` and DRG profile lineage).
3. The Op runs under that context and is closed with its real outcome.

## Runtime/Execution Domain Detail

See [Runtime/Execution Domain (Container Detail)](runtime-execution-domain.md)
for the canonical work-package lifecycle FSM, transition-guard summary, and
execution/routing invariants.

## Interaction Constraints

1. State transitions are host-authoritative; orchestrator, Team Kitty, the relay,
   and trackers use contract surfaces only.
2. Modules communicate through OHS facades; `status` internals are import-forbidden
   outside Mission Management.
3. There is exactly one execution-state surface (`mission_runtime`) and one
   commit-protection decision (`commit_guard.evaluate`).
4. Hosted and tracker integrations are optional and boundary-scoped; hosted
   moments are opt-in on the client (drain) and never block local persistence.

## Decision Traceability

<!-- DECISION: 2026-06-03-1 - Four bounded modules; status owned exclusively by Mission Management -->
<!-- DECISION: 2026-06-07-1 - mission_runtime is the canonical execution-state surface -->
<!-- DECISION: 2026-06-03-2 - CommitTarget(ref, kind) is the one destination; GuardCapability asserts authorization -->

## Traceability

- Domain model ADR: [`docs/adr/3.x/2026-06-03-1-execution-state-domain-model.md`](../../../adr/3.x/2026-06-03-1-execution-state-domain-model.md)
- Canonical execution surface ADR: [`docs/adr/3.x/2026-06-07-1-execution-state-canonical-surface.md`](../../../adr/3.x/2026-06-07-1-execution-state-canonical-surface.md)
- ExecutionContext owner + CommitTarget ADR (incl. 2026-06-10 addendum): [`docs/adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md`](../../../adr/3.x/2026-06-03-2-executioncontext-owner-and-committarget.md)
- Shared package boundary ADR: [`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`](../../../adr/3.x/2026-04-25-1-shared-package-boundary.md)
- Runtime/execution detail: [`runtime-execution-domain.md`](runtime-execution-domain.md)
- Context view: [`../01_context/README.md`](../01_context/README.md)
- Component view: [`../03_components/README.md`](../03_components/README.md)
- Charter service strangler ADR: [`2026-10-03-1`](../../../adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md)
