---
title: 'ADR: gate bindings reuse `mission_step_contract` — the content-vs-relationship principle'
description: 'Gate bindings reuse `mission_step_contract` instead of earning a kind: promote only distributable content artefacts, attach relationships and configuration to existing ones.'
status: Accepted
date: '2026-07-22'
---

**Status:** Accepted

**Date:** 2026-07-22

**Deciders:** Operator (Stijn Dejongh); recorded by the plan-phase architect
(`architect-alphonso`) per post-plan-squad finding C-C4.

**Technical Story:** epic [#2535](https://github.com/Priivacy-ai/spec-kitty/issues/2535)
(doctrine-controlled transition gates, half A); tracker
[#2468](https://github.com/Priivacy-ai/spec-kitty/issues/2468) (the decision-record
obligation this ADR discharges); spec constraint C-001; sibling ADR
[2026-07-21-2-glossary-first-order-doctrine-artefact.md](2026-07-21-2-glossary-first-order-doctrine-artefact.md)
(the precedent this ADR reconciles).

---

## Context and Problem Statement

Half A of the doctrine-controlled transition gates mission (#2535) needs gate handlers
to bind to activation — a repo's active doctrine should decide which handler fires on a
`for_review` transition, not a hardcoded repo-shape probe. The open design question is
*where that binding lives*: does a gate binding need its own first-class, charter-activatable
`ArtifactKind` (a `gate` kind, joining `directive`, `tactic`, `glossary_pack`, etc. in the
activatable universe), or does it attach to an artefact that already exists?

This question was flagged for a decision record by tracker #2468 and by the post-plan
adversarial squad (finding C-C4), because the mission has a **visible opposite precedent
in the same doctrine layer, decided one day earlier**: ADR
[2026-07-21-2](2026-07-21-2-glossary-first-order-doctrine-artefact.md) promotes
`GLOSSARY_PACK` to a first-class, charter-activatable `ArtifactKind`. Without an explicit
rule, a reader lands on "glossary got its own kind" and "gate binding did not" back-to-back
and reasonably reads it as inconsistency rather than principle.

## Decision Drivers

- **C-001** (primary) — the spec constraint: gate handlers bind through the existing
  `mission_step_contract` kind; no new activatable `gate` `ArtifactKind`; the rationale
  must be a durable principle, not merely the #2468 cost, recorded in an ADR at plan time.
- **Single canonical authority** (charter governing principle) — one rule should explain
  both this decision and the glossary decision, or the doctrine layer's own artefact-kind
  boundary looks arbitrary.
- **#2468 decision-record obligation** — a kind-boundary call of this shape must leave a
  citable record, not a retro-justification discoverable only in code review.
- Frames **C-002** (native handlers only, half A) and **FR-006** (bindings resolve through
  the existing activatable kind) — this ADR is why FR-006 is shaped the way it is.

## Considered Options

- **Option 1 (chosen)** — Reuse `mission_step_contract`: a gate binding is a new field,
  `gates: list[GateBinding]`, on the existing `MissionStepContract` model, authored in
  `review.step-contract.yaml`. No new `ArtifactKind`, no new enumeration surface.
- **Option 2 (rejected)** — Promote a first-class `gate` `ArtifactKind`, mirroring the
  glossary-pack precedent: its own DRG node kind, its own URN prefix, its own place in the
  charter-activatable universe.

## Decision Outcome

**Chosen option: Option 1 — reuse `mission_step_contract`.**

### The principle

Whether a concept earns its own first-class `ArtifactKind` turns on **what kind of thing
it is**, not on how important or how novel it is:

- **PROMOTE** a concept to a first-class, charter-activatable `ArtifactKind` when it is a
  new **distributable content artefact** — it ships its own files, has its own repository
  of instances, carries its own provenance, and is meaningfully migrated, versioned, and
  activated as a unit independent of any other artefact. The glossary pack is this shape:
  `*.glossary-pack.yaml` files, a migratable 104-term corpus, its own `glossary_pack:` URN.
- **REUSE / ATTACH** when the concept is a **relationship or configuration** expressed
  *on* an artefact that already has its own first-class identity. It has no files,
  repository, or provenance of its own — it is a field that configures how the existing
  artefact behaves at a named point. A gate binding is this shape: it does not exist
  independent of the step contract it configures; it says "when this contract's
  `for_review` edge fires, call this named handler." It is the field
  `gates: list[GateBinding]` on `MissionStepContract`, authored inline in
  `review.step-contract.yaml` — not a standalone file type, not a separate corpus, not
  something a project would ever activate or deactivate on its own apart from the contract
  it lives on.

Applied here: a gate binding rides the `mission_step_contract` kind's *existing*
activation, resolution, and DRG wiring. It needs no new enumeration surface — no new entry
in `pack_context._BUILTIN_ARTIFACT_KINDS`, `activations._ALLOWED_KINDS`, or
`org_pack_loader._ORG_DRG_CANONICAL_KINDS` (the three mirrored kind-lists the glossary ADR
names as drift-guarded). This is exactly what FR-006 requires: bindings resolve through the
existing activatable kind, with no new `gate` `ArtifactKind`.

### Reconciling the glossary precedent (squad finding C-C4)

The glossary ADR and this ADR reach opposite conclusions — **promote** vs **reuse** — from
the **same governing rule**, because the two artefacts differ in kind, not in importance:

| Dimension | Glossary pack | Gate binding |
| --- | --- | --- |
| **Nature** | New distributable content | Relationship/configuration on an existing artefact |
| **Has its own files?** | Yes — `*.glossary-pack.yaml` | No — a field inside `review.step-contract.yaml` |
| **Has its own corpus/instances?** | Yes — 104 migrated terms, growable independently | No — bindings are inline entries on one contract |
| **Has its own provenance/URN?** | Yes — `glossary_pack:` | No — inherits the contract's `mission_step_contract:` identity |
| **Independently activatable?** | Yes — a project can carry a pack with no gates and vice versa is meaningless the other way | No — a binding has no existence apart from the contract it configures |
| **Outcome under the rule** | **Promote** to a first-class `ArtifactKind` | **Reuse/attach** as a field on an existing kind |

Read together, the two ADRs are not a contradiction: they are the **same rule applied
correctly to two different shapes of thing**. A future reader who lands on either ADR
should follow the cross-link to the other and see one principle, not two ad hoc calls.

### Rejected: Option 2 (promote a `gate` `ArtifactKind`)

Rejected on the content-vs-relationship rule itself: a gate binding has no independent
files, repository, or provenance — promoting it would misclassify a relationship as
content. It also fails the #2468 cost test the glossary ADR already names as load-bearing:
a new kind means growing the three mirrored, drift-guarded kind-lists
(`pack_context._BUILTIN_ARTIFACT_KINDS`, `activations._ALLOWED_KINDS`,
`org_pack_loader._ORG_DRG_CANONICAL_KINDS`) for a concept that has nothing to enumerate on
its own. The cost is corroborating evidence, not the reason — the reason is the principle
above.

### Consequences

**Positive**

- One principle explains both the glossary promotion and the gate reuse; no artefact-kind
  boundary call in this doctrine layer reads as arbitrary.
- FR-006 is satisfied for free: bindings resolve through existing activation with zero new
  enumeration surfaces to keep in sync.
- The schema work (data-model.md §3, `GateBinding`) can proceed on a settled, cited
  foundation instead of an implicit assumption discovered during review.

**Negative**

- A gate binding is invisible to any tooling that lists `ArtifactKind` values directly
  (e.g. a future "what kinds exist" report) — it is only discoverable by reading the
  `mission_step_contract` schema. This is the expected shape for a field, not a defect.
- If a future need arises for gate bindings to be independently distributable (their own
  files/provenance, shared across contracts) the classification would flip and Option 2
  would need to be reopened as a new decision, not retrofitted onto this one.

**Boundaries** — this ADR does not define the `GateBinding` field shape, the resolution
join, or the lane→contract ownership mapping; those are IC-04's schema work
(data-model.md §3). It records only the kind-boundary principle and its application.

## Related ADRs

- [2026-07-21-2-glossary-first-order-doctrine-artefact.md](2026-07-21-2-glossary-first-order-doctrine-artefact.md)
  — the **promote** precedent this ADR reconciles: same content-vs-relationship rule,
  opposite outcome, because the glossary pack is new distributable content and a gate
  binding is a relationship on an existing artefact.
- [2026-05-16-1-doctrine-layer-merge-semantics.md](2026-05-16-1-doctrine-layer-merge-semantics.md)
  — the governing doctrine-integrity ADR; this decision operates inside its artefact-kind
  and activation model.
