---
title: '04 — Doctrine Constraints: The Rules Any Domain Split Must Obey'
description: 'Doctrine constraints for the runtime and state overhaul: the binding governance artifacts any domain split must obey, with directive enforcement levels noted.'
doc_status: deprecated
updated: '2026-06-03'
---
# 04 — Doctrine Constraints: The Rules Any Domain Split Must Obey

These are **binding** governance artifacts from `src/doctrine/`. They are not advice; DIRECTIVE
enforcement levels are noted. Any proposed domain split in `06` is checked against this list.

---

## Binding directives

### DIRECTIVE_001 — Architectural Integrity Standard *(enforcement: required)*

`src/doctrine/directives/built-in/001-architectural-integrity-standard.directive.yaml`
> "System designs must maintain clear separation of concerns and well-defined component boundaries so
> that each part of the system is independently understandable, testable, and replaceable without cascading changes."

Core rules:
- Components must **not share mutable state across boundaries** without an explicit, documented protocol (`:19`).
- **No circular dependencies** unless intentional, bounded, justified in an ADR (`:20`).
- Boundary violations found in review **must be resolved before merge** (`:21`).

### DIRECTIVE_031 — Context-Aware Design *(enforcement: required)*

`031-context-aware-design.directive.yaml`
> "Every design decision must be made with explicit awareness of the bounded context it belongs to …
> Crossing a context boundary requires an explicit translation layer; implicit coupling across boundaries is prohibited."

Core rules:
- **No direct object references across bounded context boundaries.** Integration via well-defined interfaces or events (`:27-28`).
- Domain terms consistent with the context glossary; deviations need documented rationale (`:29-30`).
- **No shared mutable state between contexts** without an explicit Shared Kernel agreement + coordination protocol (`:31-32`).
- Avoid generic names (`Manager`, `Handler`, `Data`, `Utils`) that obscure domain meaning (`:18-19`).

### DIRECTIVE_032 — Conceptual Alignment *(enforcement: required)*

`032-conceptual-alignment.directive.yaml`
> "Agents must never assume that shared vocabulary implies shared meaning … state its interpretation
> of each key term and confirm that interpretation with the requester."

Core rules:
- May **not proceed to implementation while unresolved ambiguities exist** in key terms (`:28-29`).
- Confirmed interpretations **must not be silently revised** mid-task (`:30-31`).
- Record the confirmed interpretation in the task artefact/ADR (`:25-26`).

> **Direct application to this overhaul:** the terms `MissionExecutionContext`, "execution
> workspace", "coordination", "mission run", "target branch", "destination ref" are exactly the
> overloaded vocabulary DIRECTIVE_032 targets. The glossary work and the ADR naming must precede
> implementation. (See `06` open questions.)

### DIRECTIVE_024 — Locality of Change *(enforcement: lenient-adherence)*

> "Changes should stay close to the problem … Unrelated refactors must not be mixed into scoped implementation tasks" (`:16`).

> Tension to manage: a context-unification touches the densest coupling cluster in the repo. The
> migration must be **incremental (Strangler Fig)**, not a big-bang refactor, to honor both
> DIRECTIVE_024 and the bus-factor / DM-D constraint from `03`.

---

## Paradigms (worldview the design should express)

### Domain-Driven Design — `paradigms/built-in/domain-driven-design.paradigm.yaml`

Strategic design = decompose into **Bounded Contexts** connected by explicit **Context Mapping**
(ACL, OHS, Shared Kernel, Published Language…). Each context holds **one Ubiquitous Language**.
Tactical patterns (Aggregates, Entities, Value Objects, Domain Events, Repositories, Domain Services)
enforce invariants at the model boundary. **Opposed by** `anemic-domain-model`, `big-ball-of-mud`,
`database-driven-design`. References DIRECTIVE_001/031/032.

### Deep Module Design — `paradigms/built-in/deep-module-design.paradigm.yaml`

> "Shape modules so a small, stable interface gives callers high leverage over a substantial
> implementation … changes, bugs, and knowledge concentrate behind the interface instead of spreading across callers and tests."

> **Application:** the entire #1619 problem is a *shallow-interface* problem — callers each know the
> full topology. A `MissionExecutionContext` should be a **deep module**: small interface
> (`status_read_dir`, `status_write_dir`, `destination_ref`, …), substantial hidden topology logic.

---

## Tactics (the procedures we should actually run)

| Tactic | What it gives this effort |
|--------|---------------------------|
| **Bounded Context Identification** (`tactics/.../analysis/`) | Boundaries are found by **language divergence** (same word ≠ same meaning), not technical layers. Failure modes: forced unification, invisible boundaries, **boundary-by-technology**, over-splitting. |
| **Context Boundary Inference** | Use Conway's Law + terminology-conflict clusters + git vocabulary-ownership. Success requires **no shared mutable state across boundaries**. Failure: >3 contexts for a small system = artificial. |
| **Context Mapping Classification** | Classify every context pair with the 9 patterns (OHS, Published Language, Conformist, **ACL**, Customer/Supplier, Partnership, Shared Kernel, Separate Ways, Big Ball of Mud). |
| **Anti-Corruption Layer** | Translate at the boundary through a **single chokepoint**; no business logic in the ACL; no direct calls bypassing it. |
| **Aggregate Boundary Design** | Group objects by **invariant scope**; one root per aggregate is the sole mutation entry point. Failure: god aggregate, leaking internals, invariant blindness. |
| **Domain Event Capture** | Persist immutable events **before** processing; separate recording from reaction; design for idempotent replay. (Spec Kitty's status log already embodies this.) |
| **Language-Driven Design** | Treat language drift as an architectural signal: same-term/multiple-meaning ⇒ hidden context boundary; vague terms (`Manager`, `Handler`) ⇒ leaky abstraction. |

---

## Styleguide — Aggregate Design Rules

`styleguides/built-in/aggregate-design-rules.styleguide.yaml`
- Reference other aggregates **by identity only** — never a direct object reference (`:7`).
- **Keep aggregates small**; split if parts change independently and don't share invariants (`:8`).
- Cross-aggregate workflows coordinate via **domain events**, not shared mutable state (`:9`).
- Quality test: *"Can each aggregate be loaded, modified, and persisted in a single transaction without touching any other aggregate's state?"* (`:73`).

---

## Dependency-direction rule (from current architecture)

`charter` and `doctrine` must **not** import from `specify_cli`; `specify_cli` imports from both.
This clean direction is a protected invariant — the redesign may not invert it.

---

## The hard-constraint checklist (used to vet `06`)

1. **Boundaries by ubiquitous language, not by runtime stage.** (DIRECTIVE_031; the charter
   `lifecycle/read-only/check` split is the named anti-example.)
2. **No shared mutable state across context boundaries.** (DIRECTIVE_001/031; the #1602
   `status.events.jsonl` collision is a live violation inside the status domain.)
3. **Every cross-boundary crossing is an explicit interface/event/ACL chokepoint** — no direct reach
   into another context's files/models. (DIRECTIVE_031; the residue raw `repo_root/"kitty-specs"`
   reads in `02` are violations.)
4. **No new circular dependencies; preserve `doctrine ← charter ← specify_cli`.** (DIRECTIVE_001.)
5. **Resolve overloaded vocabulary before building** (Mission/Mission Run, execution workspace,
   destination ref). (DIRECTIVE_032.)
6. **Deep modules / aggregates by invariant scope; identity-only references; coordinate by events.**
   (Deep Module Design; Aggregate Design Rules.)
7. **Incremental migration (Strangler Fig), not big-bang** — honor Locality-of-Change + bus-factor risk.
8. **≤ a small number of new contexts** — over-splitting is an explicit failure mode.
