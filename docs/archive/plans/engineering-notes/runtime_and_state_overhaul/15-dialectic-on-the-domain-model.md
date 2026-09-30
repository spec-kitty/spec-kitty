---
title: 15 — Dialectic on the Refined Domain Model
description: Consolidation-gate dialectic (Phase 2) on the refined Tier-1 domain model from note 14, corroborating then refuting and reconciling for the overhaul.
doc_status: deprecated
updated: '2026-06-03'
---
# 15 — Dialectic on the Refined Domain Model

**Phase:** 2 (consolidation gate) · **Date:** 2026-06-03 · **Method:** `dialectic-research` tactic
(corroborate ‖ refute → reconcile). Target: the Tier 1 domain model in `14` as refined across the
Tier-1 / cross-tier rounds.

> **Verdict: the *structural core* survives; the *strategic-DDD labeling* mostly does not.** The
> Mission-aggregate ≠ MissionRun-aggregate cut is sound (ADR-mandated, CI-enforced, 1:many). But
> **three of the four recent refinements** — Context-as-subdomain-of-Execution, Actor-realized-in-Execution,
> Prompt-as-DTO — are **refuted**, and the phase-flavored domain naming is **weakened**. Notably, the
> refutations are grounded largely in **our own earlier docs (`03`, `06`, `09`)** and the code — i.e.
> the last few turns *regressed* from more careful earlier framing. This document is the consolidation
> gate the design must pass before mapping to `06`.

## Verdict table

| # | Claim under test | Verdict | Why |
|---|------------------|---------|-----|
| V1 | "Mission Management vs Execution" is a bounded-context split | **WEAKENED** | Boundary is real but **identity-keyed, not phase-keyed**; the *naming* ("intent/planning vs doing") is phase language; the ubiquitous language (Mission/WP/lane/status) **spans both** |
| V2 | Context = supporting **subdomain of Execution** | **REFUTED** | Identity/path/status resolution is consumed by planning, dashboard, acceptance, merge — it is a **Shared Kernel / Open-Host context**, owned by none |
| V3 | Actor **realized in Execution** | **REFUTED as stated** | Our own BPMN puts the Operator in Governance (charter) and Integrate (merge); Actor is **cross-domain**; only the LLM-agent step-execution is execution-bound |
| V4 | Executor Prompt = **DTO** (2-domain boundary) | **REFUTED** | It is a **generated, governed projection = Published Language** (OHS wire format), assembled from **4** inputs (MM + Governance + Context + consumed-by-Actor), not a dumb 2-party carrier |
| V5 | The 3-domain model **refines** the deep-dive context map | **REFUTED as "faithful"** | It **fuses Charter+Doctrine** (two clean contexts), **dissolves Status/kanban**, drops Dashboard/Glossary, and invents names with no code referent |

## Reconciliation (strongest from each side)

### V1 — keep the cut, re-anchor the name

Both passes agree the **substance** is sound: `Mission` (`mission_id`, durable, `kitty-specs/`, git) and
`MissionRun` (`mission_run_id`, ephemeral, `.kittify/runtime/`) are distinct aggregates, **1:many**,
ADR `2026-04-04-2`-mandated, CI-enforced (`13`). **But** `status/` (`MissionStatus`, `lane_reader`,
`work_package_lifecycle`) is consumed by **both** planning (`agent/tasks.py`) and runtime
(`runtime/next/discovery.py`, `decision.py`) — one ubiquitous language across both claimed domains.
→ **Revision:** name the boundary by **aggregate identity** (Mission vs MissionRun), not by phase
("intent/planning vs doing"); surface **Status/kanban as a shared context** both consume, don't fold it into "Mission Management".

### V2 — Context is a Shared Kernel / OHS, not an Execution subdomain

Decisive, and self-grounded: the dashboard/kanban read path `agent_utils/status.py:131` calls
`resolve_mission_identity` to render a board (pure Mission-Management/visibility); `resolve_mission_read_path`
is consumed by `acceptance/`, `merge/`, `agent/tasks.py` (finalize/planning). **Our own `06` already
typed this as OHS** ("Command surfaces → Operation Context: **OHS** — one published way to get an
operation's context", `06` §3) and **`09` flagged F1 as ambient** ("may not belong inside the mission
composite… already injected via DoctrineService", `09` §2/§8). → **Revision:** reclassify Context as a
**Shared Kernel / Open-Host Service** consumed by Governance-read, Mission Management, **and** Execution.
Drop "subdomain of Execution." *(This reverses the cross-tier refinement #2.)*

> Definitional note: the corroborator narrowly scoped "Context" = the `ActionContext` class (only 2
> files, execution-concentrated). But our model defines Context **broadly** (Identity · Filesystem ·
> VC · status snapshot = the `09` fragments). Under our own definition, the broad set is shared → V2 refuted.

### V3 — Actor is cross-domain; only step-execution is execution-bound

The model's **own swimlane** (`14` Process view) puts the Operator at `charter interview` (Governance)
and `merge go/no-go` (Integrate) — change-effecting acts outside Execution. → **Revision:** Actor is a
**cross-domain metamodel** spanning Governance, Mission Management, and Execution by actor-kind/phase.
The defensible narrow claim: *an LLM agent's realization of an issued step* is execution-bound. Don't
generalize to "Actor realized in Execution." *(Refines cross-tier refinement #3.)*

### V4 — Executor Prompt is a Published Language, not a DTO

It is **rendered** ("fuse profile × action × gov-context × environment → render prompt", `14` sequence)
and is "the agent's entire sensorium" — a generated, governed projection. `09` already derives
`PromptContext` *by composition from fragments* (a projection, not a carrier). And it draws from **four**
sources (MM intent/WP + Governance rules/profile + Context environment, consumed by the Actor) — a
4-way junction, not a 2-party DTO. → **Revision:** retype as the **Published Language of the
governed-invocation Open-Host Service** — a projection rendered from Governance + Context + Mission
Management, consumed by the Actor. *(Refines cross-tier refinement #4: the "boundary object" intuition
is right; "DTO" and "2-domain" are wrong.)*

### V5 — reconcile cell-by-cell with the deep-dive, don't re-cut

The deep-dive (`03` B) names **Charter** and **Doctrine** as two separate clean contexts (zero inverse
imports, separate `src/charter/` + `src/doctrine/` packages) and **Status/kanban** as its own bounded
context. The Tier-1 model fuses Charter+Doctrine into "Governance" and dissolves Status/kanban →
lower resolution, not a refinement. → **Revision:** express "Governance" as an **umbrella over two
contexts** (Charter ⊕ Doctrine); surface **Status/kanban** as a shared context; keep Dashboard/Glossary
on the map; map every domain name to an existing package/context or mark it as net-new
(`mission_runtime/` does not exist yet — grep for "Mission Management" in `src` returns zero).

## What survives (the keepers)

- **Mission aggregate ≠ MissionRun aggregate** — 1:many, ADR-mandated, CI-enforced. The load-bearing cut.
- **MissionType ∈ Governance** (doctrine artifact) — uncontested.
- **The `09` derivation/composition model** (fragments by domain × scope, composites per operation) —
  it already self-corrects toward Shared-Kernel/OHS and away from the Tier-1 errors. **`09` is closer
  to right than the later Tier-1 refinements.**
- The **execution spine** (MissionRun issues MissionStep → targets WorkPackage) — internally consistent and code-backed (`issued_step_id`).
- The **MissionRun-can't-name-its-Mission degeneracy** as a real, separable finding (`13`).

## Consolidation checklist (do before mapping to `06`)

1. Re-name the Mission/MissionRun boundary by **identity**, not phase.
2. Reclassify **Context → Shared Kernel / OHS** (per `06`/`09`); remove "subdomain of Execution".
3. Re-scope **Actor → cross-domain**; keep only "LLM step-execution is execution-bound".
4. Retype **Executor Prompt → Published Language / OHS projection** (4-way), not 2-domain DTO.
5. **Surface Status/kanban** as a shared context; **un-fuse Charter + Doctrine** under the Governance umbrella.
6. Map each domain box to an **existing package/context** (`03`) or mark **net-new**.

## Impressions (architect)

This is the dialectic earning its keep. The last three turns of refinement were *intuitive and
fluent* but drifted into **strategic-DDD labels that the project's own code and prior maps don't
support** — and crucially, **`09` already had it more right** (OHS/Shared-Kernel, projection-not-DTO).
The healthy reading: our **structural** instinct (durable Mission vs ephemeral MissionRun, the
execution spine) is solid and ADR-anchored; our **strategic-design vocabulary** got ahead of the
evidence. Consolidating items 1–6 — largely by reconciling Tier-1 back toward `09` + `03` — makes the
model internally consistent and ready to map onto `06`. The next phase (codebase reassessment) should
**validate the sharpened hypotheses** this dialectic produced (Context is shared; status-language
spans planning+runtime; Actor is cross-domain; prompt is a governed projection; MissionRun degeneracy).
