---
title: Session Recap — Runtime & State Overhaul (Architecture Phases 1–2)
description: 'Session recap of Architecture Phases 1-2 of the runtime and state overhaul (2026-06-03), summarizing the grounding and conceptual-modeling work for #1619.'
doc_status: deprecated
updated: '2026-06-03'
---
# Session Recap — Runtime & State Overhaul (Architecture Phases 1–2)

**Date:** 2026-06-03 · **Participants:** Stijn Dejongh + Architect Alphonso (Claude)
**Issue:** [Priivacy-ai/spec-kitty#1619](https://github.com/Priivacy-ai/spec-kitty/issues/1619)

This is the **narrative** companion to the numbered grounding docs (`01`–`09`). It exists so a
contributor joining the thread can follow *how* we got here, not just the conclusions. If you only
read two files, read `08` (the checkpoint) and `09` (the model); this recap tells the story between them.

---

## Why we started

Spec Kitty keeps shipping point-fixes for the same kind of failure: agents manually hopping between
the main checkout, the coordination branch, and lane worktrees; dependency checks reading stale
state; `safe_commit` telling people to check out branches that fight the orchestration topology;
prompts that describe a topology the CLI no longer uses. PR #1627 closed four concrete child bugs
(#1615–#1618), but the parent epic #1619 stayed open because the *structural* cause was untouched.
Stijn framed the goal: design a to-be state that makes this whole class of problem stop recurring,
then start shifting the codebase toward it.

We did this in the architect role, treating it as a grounding-then-design exercise: gather evidence
first, commit to a design later, keep the doctrine honest throughout.

## How the investigation unfolded

**1. Capture the tickets (`01`).** We read #1619 and every linked issue (#1615–#1618, the related
issues #1602 and #1348, and the #1627 fix). The pattern was unmistakable across all of them: *split
authority*. Writes go to the coordination branch; many reads and all the prompts still assume the
main checkout or the target branch. Six tickets, one disease.

**2. Map the current code (`02`).** A read-only survey of how ~40 surfaces derive "where is this
mission's state." The finding that reframed everything: the `status/` domain is *already clean* and
event-sourced — the defect isn't in how state transitions, it's in how each caller independently
decides *where state lives and where commands may run*. That decision — **topology resolution** —
has no owner. Two half-resolvers already exist (`resolve_mission_read_path` for reads,
`BookkeepingTransaction` for writes) and they re-derive the same identity tuple separately, via four
duplicated path-builders.

**3. Read the architecture and the doctrine (`03`, `04`).** The 3.x ADRs already commit to a lot we
must honor: lanes own git, WPs own accounting, ULID identity, atomic WP-start as a *service*,
`approved` ≠ `done`, and — crucially — the **Mission Type / Mission / Mission Run** ontology that
tells us the new object is a *Mission Run* concern. The CAACS audits confirmed this is the repo's
densest, most complex, least-tested cluster (bus factor ≈ 1), and that the team already filed epic
number #992 "centralize domain invariants." The DDD doctrine (DIRECTIVE_001/031/032) gave us hard rules:
boundaries by ubiquitous language not runtime stage, no shared mutable state across boundaries,
resolve overloaded vocabulary *before* building.

**4. Synthesize (`05`).** One sentence: *execution context is computed by every caller instead of
owned by one model, so the physical truth is reconstructed — differently — at ~40 sites, and the
gaps are the bug class.* We wrote down ten invariants (I-1…I-10) any design must satisfy, and the
list of things already-good that we must **not** break.

**5. First design pass (`06`).** Proposed a bounded-context decomposition and three design options
(value object / operation service / strangler façade), explicitly leaving the choice open.

## The two pivots that changed the design

**Pivot A — "mirror what already exists" (`07`).** Stijn's instinct was to model the new context the
way the codebase already models doctrine/charter infrastructure. Investigating that, we found the
pattern isn't just present — it's *already partly wired for this purpose*. `DoctrineService` +
`PackContext` + `ProjectContext` are the exact "roots-as-data + frozen snapshot + pure assembler +
higher-layer builder" shape. And `OperationalContext` **already exists** as a class — except it
holds *session* facts (model/profile/role), not filesystem aspects. That naming collision became a
design input, not a footnote. We also assessed the two requested extractions: **MissionStatus** is a
near-free aggregate (event-sourcing already gives us hydration + invariants), and **MissionFlow** is
~80% built as a pure FSM — but is hardcoded and identical across all mission types, so "make it
mission-type-driven" is net-new work that should be its *own* later epic, not smuggled into #1619.

**Pivot B — "context is a composition, not an object" (`09`).** Stijn's hypothesis: the flat
`MissionExecutionContext` field list is really several *domain-owned chunks* — infrastructure,
filesystem, version control, execution preferences, execution state — that should be modeled
individually and **composed** per purpose. This turned out to be the key. Classifying every field on
two axes (domain × scope) and separating primitive from derived information, the flat object
dissolves into six fragments — four of which already exist in some form. The collision from Pivot A
resolves cleanly: the existing `OperationalContext` simply *is* the execution-preferences fragment;
the filesystem concept is a *different* fragment. Composites (`ReadContext`, `WriteContext`,
`PromptContext`, …) are assembled from fragments per operation — which is how the atomicity invariant
(I-4) and prompts-from-context (I-6) become true *by construction* rather than by discipline.

## Phase 2 continued (2026-06-03, same session)

After the first commit we kept going, and the work took two important turns:

**Requirements capture (`10`).** We switched to specifying *what must be known* by each actor
(code/user/agent) at each lifecycle step, across six dimensions, using three lenses **in order**:
intuition → docs → code. Two facts looked conspicuously *unowned*: mission **phase** and
**interaction policy** (parallelism/merge/workspace). Stijn added two corroborating intuitions — that
behaviour binds to runtime state via an **activity ledger**, and that interaction strategy is usually
a **charter default** overridable per run.

**The dialectic (`11`).** We ran a corroborate-vs-refute pass (two agents, Architect Alphonso framing).
The refutation landed real hits and **none of our four claims survived intact** — which was the most
valuable outcome:
- We were about to **reinvent `ActionContext`** (`core/execution_context.py:44`), which already
  composes domain-owned context and is backed by an accepted ADR (2026-03-09-1, "prompts don't
  discover context, commands do"). → **Harden `ActionContext`, don't greenfield.**
- "Behaviour wrongly frozen" was wrong — behaviour is already resolved *live*; run-start freezing of
  *topology* is a deliberate determinism contract (ADR 2026-02-17-1). Real fix = **one owner** for
  profile resolution.
- Interaction policy should be **resolved-and-frozen at plan time** (honoring the fail-closed
  `lanes.json` ADR 2026-04-03-1), not per-run-mutable.
- Mission "phase" is **distributed-first-class** already (`MissionOrchestration.states`, `MissionRunSnapshot`,
  `WPState`); don't add a new enum — derive or wire.

**The actor mental model (`12`).** Stepping up a level, Stijn framed an actor as needing a **sense of
self, purpose, and environment** — which maps onto AgentProfile (self), MissionRun + Charter
(purpose), and Context (environment). The punchline: **for an LLM agent the runtime is its sensory
organ** — the prompt is its entire sensorium — so #1619 is really about *fixing the agent's
perception of its environment*, not about paths. Refinements from Stijn folded in: **Constitution ==
Charter** (Constitution deprecated); **Activity Ledger = MissionRun state**; **Actor is a metamodel
concept** disambiguating into AgentProfile / Operator(Human-In-Charge) / External System; this model
will likely become a published `docs/architecture/` doc once crystallized.

**Dialectic on "Mission ≡ MissionRun" (`13`).** Stijn proposed Mission and MissionRun are one concept
(Mission = deprecated alias). A corroborate/refute run **refuted** it: the relationship is **1:many**
(ephemeral query runs + cleanup re-runs), with distinct storage/id/lifecycle and a standing ADR that
explicitly rejected collapsing them. Salvaged truths: (a) the **layered state** belongs to the
**Mission**, not the Run — correcting `12` §5a; the **Mission Run** is the ephemeral 1:many *driver*;
(b) Mission Run is **degenerate in code today** (uuid/proxy; its snapshot doesn't even reference its
Mission) — a real smell adjacent to #1619. We also captured **dialectical research itself as a
doctrine tactic** (`src/doctrine/tactics/built-in/analysis/dialectic-research.tactic.yaml`, registered
in the DRG).

**Model diagrams + domain remediation (`14`).** Compiled the concept map into a multi-tier set
(Tier 1 domains + interrelations, Tier 2 drill-downs, a BPMN swimlane, and the governed-invocation
sequence). Stijn then refined the domain model: **three top-level domains** — **Governance** (beliefs
& rules), **Mission Management** (intent & planning, durable), **Execution/Runtime** (the doing,
ephemeral) — with **Context/Environment a supporting *subdomain* of Execution**, **Actor realized in
Execution** (beliefs sourced from Governance), and the **Executor Prompt a boundary DTO** between
Mission Management and Execution (aligned via Governance + Context). Mission is a *concept* in Mission
Management (not Runtime — ADR 2026-04-04-2 planning/runtime split); MissionType is a Governance artifact.

**Dialectic on the refined design (`15`).** Stress-tested the Tier-1 domain model. The **core
survives** (Mission-aggregate ≠ MissionRun-aggregate; 1:many; ADR+CI backed), but **three recent
refinements were refuted**, mostly by our *own* earlier docs (03/06/09) and code: Context is a **Shared
Kernel / OHS** (not a subdomain of Execution); **Actor is cross-domain** (the swimlane itself puts the
Operator in Governance + Integrate); the **Executor Prompt is a Published Language / OHS projection**
(4-way), not a 2-domain DTO. Lesson: the last turns' strategic-DDD *labels* got ahead of the evidence;
`09` was closer to right. A 6-item consolidation checklist (`15`) must be cleared before mapping to `06`.

**Codebase reassessment fan-out (`16`).** Ran a 6-agent Debbie/Pedro fan-out validating the dialectic's
sharpened hypotheses against code. **All confirmed**, plus emergent findings: Context = Shared Kernel +
OHS (H1); **Status/kanban is a first-class shared context** and the planning↔execution seam, but its
public API is bypassed ~245:6 (H2); Actor is cross-domain *and* fragmented across 3 vocabularies (H3);
the prompt is a Published Language and there are **three** parallel context projections (H4); MissionRun
can't name its Mission — `inputs["mission_slug"]` is write-only dead code (H5); and package-graph
corrections — canonical runtime is `runtime/next/_internal_runtime` (CLAUDE.md ref is **stale**),
runtime↔specify_cli is bidirectional/unenforced, `MissionStatus`/`mission_runtime/` are net-new and
layer-meta-guarded (H6). The model is validated; doc 16 is the evidence base for the `06` concretization.

**Consolidation + `06` technical mapping.** Folded Stijn's vocabulary refinements into doc 17 (Context
is per-domain — GovernanceContext/ExecutionContext/InfraContext; Shared Kernel is a code module;
Effector = Actor realized in Execution; prompt = communication artefact; "domains as bounded modules
with external API entry points" is the conceptual→technical hinge). Filed the free-wins **#1663**
(MissionRun can't name its Mission) and **#1664** (status/ public API not enforced); fixed the stale
CLAUDE.md runtime path. Rewrote **doc 06** as the technical concretization: every model element → package
home + API entry point + status (exists/to-harden/net-new), the communication-artefact + Effector
targets, and a 7-step Strangler sequence (e2e ratchet → status boundary → harden ExecutionContext →
MissionRun ref → consolidate projections → Effector → commit-seam atomicity).

**Handover:** this design set is being handed to Robert for revision, refinement, and finalization into
ADRs / stable architectural documentation, to serve as the guideline for missions addressing #1619 and
related domain-violation / architectural-design issues.

**Tickets & decisions (2026-06-03):** #992 confirmed as the **parent epic**; created **#1666**
(execution-state & context domain-boundary redesign — child of #992, **blocks** #1619) as the
implementation tracker. Decisions: **`mission_runtime/` = net-new umbrella** (Screaming Architecture +
Strangler, layer-registered); **Effector = named-in-docs for now** (materialize a code type only when
actor-kind fragmentation causes a concrete bug). Pending background-then-decision: commit-atomicity
(`worktree_root == destination_ref`) enforcement shape; communication-artefact contract. Open (no
decision): `MissionStatus` aggregate timing; vocabulary ratification.

## Where we are now

- **Phase 1 (grounding + reconnaissance): complete** — docs `01`–`08`.
- **Phase 2 (conceptual modeling + requirements): in progress** — `09` (fragment model, now reframed
  as the internals of a hardened `ActionContext`), `10` (needs capture), `11` (dialectic + revised
  claims), `12` (actor mental model). Doc `09` proposes the fragment/composite model and shows it
  satisfies every doctrine constraint while reusing existing code.
- **Decided (working consensus, post-dialectic):**
  - **Harden the existing `ActionContext`** (ADR 2026-03-09-1) and enforce its use — do NOT greenfield
    a parallel context family. The `09` fragments are its *internal structure*; keep it a deep module.
  - Complete the read/write/destination split and the `CommitTarget` (worktree==destination) kernel that
    `ActionContext` lacks today (`02`, I-2/I-4).
  - Interaction policy = **resolved-and-frozen at plan time** onto MissionRun/`lanes.json` (charter
    default → config → plan resolution → frozen), not per-run-mutable. Merge strategy may stay late-bound.
  - **Preserve** the run-start topology freeze (determinism, ADR 2026-02-17-1); fix behaviour to have a
    **single resolution owner** (frozen-step vs frontmatter divergence).
  - Don't add a `MissionPhase` enum — derive a coarse phase or wire `MissionOrchestration`.
  - Split MissionFlow into extraction-now / config-driven-later; build the #1619 e2e regression
    (main+lane CWD parity) first as the migration ratchet.
- **Actor framing (`12`):** an actor needs sense of self (AgentProfile / Operator / External System),
  purpose (MissionRun + Charter), environment (Context). For LLM agents the runtime is the sensory
  organ, so #1619 = fixing agent perception.
- **Open (next session):** harden-in-place vs Strangler-supersede for `ActionContext`; the
  Activity-Ledger→environment projection (one-writer rule); whether to model the Operator's "self";
  whether a thin shared `Actor` type is worth it; vocabulary ratification (DIRECTIVE_032); reconciling
  #1619 with epic #992; then BPMN + interaction + model diagrams.

## How to engage

- Comments/pushback most useful on `11` (revised claims) and `12` (actor model), plus the open
  questions in `11` §Next, `12` §7, `10`, and `09 §8`.
- This is **not an ADR yet** — no code has changed. ADRs follow once we pick the design shape and
  ratify the vocabulary. Nothing here is binding; it's the reasoning trail toward a decision.
