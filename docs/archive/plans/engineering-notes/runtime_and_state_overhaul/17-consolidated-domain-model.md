---
title: 17 — Consolidated Domain Model (code-validated baseline)
description: 'The consolidated, code-validated domain model (Phase 3) for the runtime and state overhaul: the internally-consistent baseline superseding the note-14 sketch.'
doc_status: deprecated
updated: '2026-06-03'
---
# 17 — Consolidated Domain Model (code-validated baseline)

**Phase:** 3 (consolidation) · **Date:** 2026-06-03 · **Status:** the internally-consistent baseline —
supersedes the `14` Tier-1 sketch. Incorporates the dialectic (`15`), the codebase fan-out (`16`), and
Stijn's conceptual refinements. This is the model we map onto `06` (technical concretization).

## Vocabulary corrections folded in (Stijn, 2026-06-03)

1. **Context is a generic, per-domain idea** — *"relevant environmental realities and ideological
   guidance."* It is correct for a Context to exist in **several** domains: **GovernanceContext**,
   **ExecutionContext**, **InfraContext**, … Each domain has *its own* Context.
2. **Shared Kernel ≠ Context.** The Shared Kernel is a **practical code-level module** holding common /
   cross-domain artefacts (path · identity · status resolvers). It is *used to build* Contexts; it is not itself a Context.
3. **Effector** is the model name for the **Actor realized inside the Execution domain**. The Actor
   (cross-domain metamodel) **correlates to** the Effector (its execution-bound realization).
4. **The Executor Prompt is a "communication artefact"** — not "Published Language" (a DDD
   context-mapping term for shared *vocabulary/schema*, not an artifact type). The earlier "DTO" framing
   was steering toward **"each domain is a bounded module with external API entry points"** — the bridge
   to the technical translation (`06`).

> Net effect on the dialectic verdicts (`15`): **V2 refines rather than reverses** — ExecutionContext
> *does* live in Execution (your original instinct), while the cross-domain resolver math is the Shared
> Kernel. **V3 resolves** via the Actor↔Effector correlation. **V4 resolves** via "communication artefact".

---

## 1. Core principles (the keepers — code-validated, `16`)

- **Mission ≠ MissionRun** — durable planning aggregate (`mission_id`, `kitty-specs/`, git) vs ephemeral
  runtime aggregate (`mission_run_id`, `.kittify/runtime/`); **1:many**; ADR `2026-04-04-2` + CI enforced.
- **MissionType / MissionStep ∈ Governance** (doctrine artifacts).
- **Execution spine**: a **MissionRun** *issues* a **MissionStep** that *targets* a **WorkPackage**.
- **Bounded module + API entry points**: each domain is a module exposing entry points (the OHS facades
  are real examples); **communication artefacts** cross between modules via those entry points.

## 2. The domains, the seam, and the shared kernel

| Element | Kind | What it is | Code home (`16`) |
|---------|------|-----------|------------------|
| **Governance** | domain | Charter ⊕ Doctrine — beliefs & rules; holds **GovernanceContext**, MissionType/MissionStep, AgentProfile | `src/charter/` ⊕ `src/doctrine/` (two clean contexts under one umbrella) |
| **Mission Management** | domain | intent & planning (durable) — Mission, WorkPackage | `kitty-specs/` + planning commands |
| **Execution / Runtime** | domain | the doing (ephemeral) — MissionRun, **ExecutionContext**, **Effector** | `src/runtime/next/_internal_runtime/` (canonical; *not* `specify_cli/next`) |
| **Status / Kanban** | **Mission Management-owned (OHS facade)** | the lane FSM + event log; owned by Mission Management, which publishes a facade — Execution/Runtime and other domains are consumers only. Decided 2026-06-03: shared-context framing was wrong; ownership prevents invariant drift. | `src/specify_cli/status/` (boundary NOT enforced → #1664) |
| **Shared Kernel** | **code module** | cross-domain commons: path · identity · status resolvers (OHS facades) | `core/paths.py`, `workspace/root_resolver.py`, `mission_metadata`, `resolve_action_context`, `resolve_mission_read_path` |

### Context is per-domain (not one box)

- **GovernanceContext** — ideological guidance: action-scoped directives/tactics + bound profile (the rules an actor must follow).
- **ExecutionContext** — environment realities for the doing: workspace, branches, read/write dirs, projected state. **≈ the hardened `ActionContext`** (the #1619 work). Lives in Execution.
- **InfraContext** — ambient install/repo realities: shipped roots, `~/.kittify`, `~/.spec-kitty` (cross-cutting).
- All Contexts are **built via the Shared Kernel** (the resolver module), but each *belongs to its domain*.

### Actor ↔ Effector

- **Actor** — cross-domain metamodel (*someone/something effecting change*); fragmented in code across 3
  vocabularies (`16` H3). Disambiguates into AgentProfile (LLM) / Operator (human) / External System.
- **Effector** — the Actor **realized inside the Execution domain**: the change-effector that consumes a
  communication artefact and acts. The only execution-bound realization (the LLM-step-executor, `16` H3).
  **Correlation:** `Effector = Actor ∩ Execution`; its *beliefs* (identity, boundaries, directives) are
  sourced from **GovernanceContext**.

## 3. Consolidated concept map

```mermaid
graph TD
  classDef dom fill:#eaf0ff,stroke:#2b4b8c,stroke-width:2px;
  classDef shared fill:#eafff0,stroke:#2b8c4b,stroke-width:2px;
  classDef seam fill:#f3e8ff,stroke:#6b2b8c,stroke-width:2px;
  classDef art fill:#fdeef6,stroke:#a3477f,stroke-width:2px;
  classDef meta fill:#fff8e1,stroke:#b8860b,stroke-dasharray:4 3;

  subgraph GOV["GOVERNANCE domain (Charter ⊕ Doctrine)"]
    GC["GovernanceContext<br/>directives · tactics · profile · action bundle"]
    MT["MissionType / MissionStep (blueprint)"]
  end
  subgraph MM["MISSION MANAGEMENT domain (durable · kitty-specs/)"]
    MWP["Mission · WorkPackage (intent)"]
  end
  subgraph EXEC["EXECUTION / RUNTIME domain (ephemeral · runtime/next)"]
    EC["ExecutionContext<br/>workspace · branches · dirs · projected state (≈ ActionContext)"]
    EFF["Effector<br/>(Actor realized in Execution)"]
    RUN["MissionRun"]
  end

  STATUS["STATUS / KANBAN<br/>Lane · StatusEvent · event log<br/><i>owned by Mission Management;<br/>published via OHS facade</i>"]:::dom
  SK["Shared Kernel (code module)<br/>path / identity / status resolvers (OHS facades)"]:::shared
  INFRA["InfraContext (ambient)<br/>shipped roots · ~/.kittify · ~/.spec-kitty"]:::shared
  PROMPT["Executor Prompt<br/>communication artefact"]:::art
  ACTOR["Actor (cross-domain metamodel)<br/>AgentProfile · Operator · External System"]:::meta

  MT -->|comprises / instantiates| MWP
  RUN -->|issues| MT
  GC -->|rules / profile| PROMPT
  MWP -->|intent / WorkPackage| PROMPT
  EC -->|environment| PROMPT
  PROMPT -->|consumed by| EFF
  EFF -->|effects change in| MWP
  ACTOR -. correlates to .-> EFF
  GC -. beliefs .-> EFF
  MM -->|owns / emits to| STATUS
  STATUS -->|WP state (read via facade)| EXEC
  GC -->|built via| SK
  EC -->|built via| SK
  INFRA -->|built via| SK
```

## 4. The three senses, re-expressed

- **Self** ← the **Effector** identity (Actor realized in Execution), with **beliefs from GovernanceContext**.
- **Purpose** ← **Mission/WorkPackage** intent (Mission Management) bounded by **GovernanceContext** rules.
- **Environment** ← **ExecutionContext** (+ ambient **InfraContext**).
- **Fusion** → the **communication artefact** (Executor Prompt) assembles all three and is consumed by the Effector.

## 5. Net-new vs existing (preview of `06`)

| Concept | Status | Home |
|---------|--------|------|
| Governance (Charter⊕Doctrine), GovernanceContext | exists | `charter/` ⊕ `doctrine/` |
| Mission Management (Mission, WP) | exists | `kitty-specs/` + planning cmds |
| Status/kanban (Mission Management-owned, OHS facade) | exists; **needs boundary enforcement (#1664)** | `specify_cli/status/` |
| Execution/Runtime, MissionRun | exists | `runtime/next/_internal_runtime/` |
| ExecutionContext (= hardened ActionContext) | exists; **to harden** | `core/execution_context.py` |
| Shared Kernel (resolvers) | exists | `core/paths.py`, `workspace/root_resolver.py`, … |
| **Effector** (named realization) | **net-new naming** (unifies fragmented Actor) | TBD |
| **`MissionStatus` aggregate / `mission_runtime/`** | **net-new** | layer-meta-guarded |
| **communication-artefact contract** (consolidate 3 projections) | **net-new** | TBD |

## 6. Open for the `06` mapping

- Where does **Effector** live as a code type (unifying the 3 Actor vocabularies, `16` H3)?
- Do the **three projections** (Prompt / ActionContext-DTO / OperationalContext-VO) consolidate into one communication-artefact contract?
- Package home for `mission_runtime/` given the layer meta-guard + the bidirectional `runtime↔specify_cli` reality (`16` H6).
- Sequencing: harden ExecutionContext (ActionContext) + enforce the Status boundary first (Strangler).
