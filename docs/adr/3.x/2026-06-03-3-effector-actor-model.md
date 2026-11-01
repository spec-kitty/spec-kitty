---
title: 'ADR 2026-06-03-3: Effector/Actor Model'
description: 'Defines an Effector as an Actor realized inside the Execution domain, but keeps it documentation vocabulary — no code type until a real bug demands one.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-06-03'
---

## Context

The spec-kitty codebase uses actor-identity vocabulary in three distinct places:

1. **Status/event log**: the `actor` field on `StatusEvent` records who
   performed a lane transition (e.g., `"claude"`, `"human"`).
2. **Retrospective log**: the actor field on retrospective entries records who
   authored an observation.
3. **Mission run engine**: the runtime-session concept of who is executing a
   mission run.

These three vocabularies are currently fragmented — they use similar words but
have no shared type and no formal relationship. The doc-01–doc-17 analysis in
issue #1666 introduced the concept of an **Effector**: the Actor as realized inside
the Execution domain.

The question is whether to materialize `Effector` as a code type now, or to
hold it as vocabulary only until a concrete need forces a code materialization.

## Decision

### Effector Is a Named Concept in Docs Only

**Definition**: An Effector is an Actor realized inside the Execution domain.
It is the execution-bound realization of an Actor: the entity that performs
actions within a mission run, producing or consuming communication artefacts
(commits, PRs, comments).

**Decision: no code type until a concrete bug triggers materialization.**

The concept is modeling vocabulary. The three existing actor-identity vocabularies
(status events, retrospective log, mission run engine) are not currently required
to share a type; they happen to use the same field name but serve different
query patterns. Materializing a `Effector` type prematurely would:

- Require join logic across three schema layers that have no current consumer.
- Create a shared type with no enforcement boundary to prevent actor-kind
  confusion from re-emerging.
- Add schema migration overhead for all three layers without delivering user value.

### Materialization Trigger

Materialize `Effector` as a code type when **either** of the following is true:

1. A concrete actor-kind-mismatch bug is filed — i.e., code confuses a status
   event actor with a run-engine actor, or with a retrospective actor, and the
   confusion causes incorrect behavior.
2. A feature requires joining status/decision/retrospective logs on actor
   identity — i.e., a query needs to answer "show me all actions by actor X
   across all three log types in a single result set."

Neither trigger is currently active.

### When Materialized: Placement

When `Effector` is materialized, it must be placed in a low-layer shared
location so all three existing vocabularies can converge:

- Preferred: `src/specify_cli/kernel/actor.py` (shared kernel layer)
- Alternative: `src/specify_cli/actor.py` (top-level if kernel does not exist)

It must not be placed inside `status/`, `runtime/`, or any single-domain
module, because the type must be importable by all three domains without
creating an illegal up-import.

### Relationship to Actor

`Actor` is the broader identity concept (who is making a request, as understood
by the governance or mission management layer). `Effector` is the execution-
domain specialization of `Actor`. The relationship is:

```
Actor (broader, may exist outside execution context)
  └─ Effector (Actor ∩ Execution domain)
```

This is a conceptual relationship, not a Python inheritance hierarchy, until
materialization.

## Consequences

### What stays the same

- All three existing actor-identity vocabularies (status events, retrospective
  log, run engine) are unchanged. They continue to use `str` or existing enum
  values for actor identity.
- No schema migration is required.
- No new code is written as part of this ADR.

### What is now explicit

- `Effector` is a named term with a definition in the project glossary and
  this ADR. Writers of architecture docs, glossary entries, and design docs
  may use the term precisely.
- The decision not to materialize is explicit, with a documented trigger for
  when materialization becomes correct.
- The placement decision (kernel layer) is pre-decided so that when
  materialization is triggered, there is no debate about where the type goes.

### What changes downstream

- No code changes from this ADR.
- WP01 adds `Effector` to the project glossary with this ADR as its reference.
- Future feature work that would trigger materialization must reference this
  ADR and document that the trigger condition was met.

## References

- Mission spec: `kitty-specs/execution-state-domain-remediation-01KT6HVH/spec.md`
- Issue #1619: Strangler Fig sequence
- Issue #1674: ADR gate requirement
- Issue #1666: doc-01–doc-17 design analysis (Effector concept origin)
- ADR [`2026-06-03-1-execution-state-domain-model.md`](2026-06-03-1-execution-state-domain-model.md): domain model gate (Shared Kernel placement)
- Glossary: `src/specify_cli/glossary/` — `Effector` and `communication artefact` entries
