# Mission Specification: Mission-type capability contract on the offering seam

**Mission Branch**: `issue-6331-mission-type-capability-offering-seam`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "#6331 — Expose the mission-type capability contract on charter.offering.api (converge with #645). Guidance: stay on the exposure half so the diffs do not collide with the sibling hardening issues #6330 (contract internals) and #6327 (the `code_producing` capability)."

## Context and Boundary

#6315 added the mission-type capability contract — `wp_driven` and
`requires_substantive_spec` — to `ResolvedMissionType` in
`charter.activation.mission_type_profiles`, the *de-facto* surface consumers already
import (`resolve_mission_type_context`). Nothing of it is on the **named** offering
seam `charter.offering.api`.

This mission closes that exposure gap and **only** that gap. It is not a re-run of
the extraction programme the issue cites: #645 is closed and #6188 is complete, and
ADR [2026-10-16-1](../../docs/adr/4.x/2026-10-16-1-extract-charter-offering-first-activation-rework-post-ga.md)
(Amendment 2026-10-19) keeps the Python charter in core behind a frozen offering seam
while `charter.activation` stays in core. The load-bearing architectural fact for the
design is the same ADR's verified dependency direction: **`charter.offering` has zero
code dependency on `charter.activation`** (the reverse edge is ~360). A "re-export the
activation DTO from the seam" reading of #6331 would invert that edge and is
therefore **out of bounds**; the *contract* crosses the seam, not the activation
implementation.

Additive seam symbols follow the amendment path ADR
[2026-10-03-1](../../docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md)
(Amendment 2026-10-19) already used for `LANGUAGE_TOKENS` (#6541): the symbol lands on
`charter.offering.api`, is named in an ADR amendment, and is narrowed by the seam's own
gates.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the capabilities through the named seam (Priority: P1)

A consumer that may only import from `charter.offering.api` (an in-core caller today, the
external charter consumer after the cutover) has a resolved mission type in hand and needs
to know whether that mission type iterates work packages and whether it demands a
substantive spec. Today it must import `charter.activation.mission_type_profiles` to read
those two facts — an undeclared dependency on an activation internal.

**Why this priority**: this is the issue. Without it the capability contract stays on the
surface the ADR says is *not* the public one, and every consumer keeps deepening a
dependency that the offering seam exists to replace.

**Independent Test**: a test module that imports the capability surface only from
`charter.offering.api` reads both capabilities off a resolved mission type and asserts the
values for the built-in families; it fails on `main` because the names do not exist on the
seam.

**Acceptance Scenarios**:

1. **Given** a consumer importing only from `charter.offering.api`, **When** it reads the
   capabilities of a resolved `software-dev` mission type, **Then** `wp_driven` is `True`
   and `requires_substantive_spec` is `True` without importing `charter.activation.*`.
2. **Given** the same consumer and a resolved `documentation` mission type, **When** it
   reads the capabilities, **Then** `wp_driven` is `False` (its action sequence declares no
   `implement` step) and `requires_substantive_spec` is `False`.
3. **Given** a resolved `research` mission type, **When** the capabilities are read through
   the seam, **Then** `wp_driven` is `False` and `requires_substantive_spec` is `True`.
4. **Given** a typeless mission (no registered mission type), **When** the capabilities are
   read through the seam, **Then** both capabilities are `False` and the read does not
   raise.

---

### User Story 2 - A typed contract, not a duck-typed convention (Priority: P2)

The consumer wants a *name* for the contract it depends on: a small, frozen value object
carrying the two capabilities, and a protocol naming the two read properties. Both live on
the offering seam, so a consumer can annotate against them and a resolver result can
satisfy them structurally without the seam knowing about the resolver.

**Why this priority**: a bare re-export of two attributes would expose the values but not
the contract; #6327 will add a third capability, and a consumer must be able to depend on
"an object that answers the capability questions" rather than on one class in one module.

**Independent Test**: `isinstance` against the (runtime-checkable) protocol holds for a
resolved mission type and fails for an object missing a capability — the negative control
proves the check is not vacuous.

**Acceptance Scenarios**:

1. **Given** the seam's capability protocol, **When** a resolved mission type is checked
   against it, **Then** the check passes and both properties are readable.
2. **Given** an object that defines only `wp_driven`, **When** it is checked against the
   protocol, **Then** the check fails.
3. **Given** the seam's capability value object, **When** it is constructed and compared,
   **Then** it is frozen (immutable) and compares by value.

---

### User Story 3 - The seam's gates stay honest (Priority: P3)

Adding symbols to the seam must satisfy, not bypass, the gates that make the seam
trustworthy: a `PUBLIC` census disposition row for the origin module, a sorted and
importable `__all__`, a charter facade that re-exports every seam symbol from
`charter.offering.api`, no no-door symbol leaking in, and the no-leak/architecture gates
that keep `charter.offering` below `charter.activation`.

**Why this priority**: the issue's second acceptance scenario is exactly this; a seam
symbol without its disposition row fails the census gate, and a seam symbol without a
facade caller fails the coverage gate.

**Independent Test**: run the named gate files; each passes, and each test that guards the
new symbols fails if the symbol is removed from the manifest (checked by inspection of the
gate's assertion, not by editing the gate).

**Acceptance Scenarios**:

1. **Given** the new origin module, **When** the census runs, **Then** the module carries a
   `PUBLIC` disposition and every reached offering path still has a disposition.
2. **Given** the new seam symbols, **When** the offering public-surface gates run, **Then**
   every symbol is importable, `__all__` stays sorted, the disposition coupling holds and a
   charter facade re-exports each symbol from `charter.offering.api`.
3. **Given** the whole change, **When** the offering layer's import graph is inspected,
   **Then** importing the capability module registers no `charter.activation` module in
   `sys.modules` and the module source imports nothing from `charter.activation`.

### Edge Cases

- **Typeless mission** (`mission_type is None`): both capabilities read `False`; the seam
  read never raises and never fabricates a mission type.
- **Custom type declaring `requires_substantive_spec: true`**: the authored value wins over
  the built-in default and is what the seam read returns.
- **Lazy resolution preserved**: `requires_substantive_spec` stays a lazy, memoised read on
  the activation side; the seam read must not turn the hot `action_sequence` path into a
  disk-reading path.
- **Agreement with the existing attributes**: the seam value equals the object's own
  `wp_driven` / `requires_substantive_spec` for every built-in family — the seam is a
  second *door*, never a second *source of truth*.
- **A third capability arrives later (#6327 `code_producing`)**: the value object gains the
  field; the protocol gains the property; no consumer-visible rename. The protocol is the
  stable part, which is why the exposure is a protocol plus a value object rather than a
  frozen tuple.
- **`wp_driven` is advisory where the frozen DAG is authoritative** (#6330 item 3): the seam
  documents that the runtime guard reads the frozen DAG, not this flag.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Capability value object on the seam | As a seam-only consumer, I want a frozen value object carrying `wp_driven` and `requires_substantive_spec` so that I can hold and compare a mission type's capabilities without importing activation. | High | Open | [build] | no — a missing symbol fails the import in the seam test |
| FR-002 | Capability protocol on the seam | As a consumer, I want a runtime-checkable protocol naming the two capability properties so that I can annotate and check a resolver result structurally. | High | Open | [build] | no — the negative control (an object missing a capability) fails if the check is vacuous |
| FR-003 | Single capability read on the seam | As a consumer, I want one read entry point that turns a capability source into the value object so that there is exactly one way to read the contract through the seam. | High | Open | [build] | no — paired with the built-in-family assertions on the same fixture |
| FR-004 | Activation conforms without changing behaviour | As a maintainer, I want `ResolvedMissionType` to satisfy the protocol and expose the value object so that the seam read returns the same values the object already carries, with no behaviour change to existing attributes or the lazy reads. | High | Open | [build] | no — a snapshot test pins all four built-in families' capabilities |
| FR-005 | Facade routing | As a runtime caller, I want the `charter.missions` facade to re-export the three seam symbols from `charter.offering.api` so that the seam has a live in-repo caller and the strict coverage gate holds. | Medium | Open | [build] | no — the coverage gate lists unre-exported symbols by name |
| FR-006 | Census disposition | As a maintainer, I want the new offering module dispositioned `PUBLIC` so that the disposition-coupling gate accepts the seam symbols. | Medium | Open | [build] | no — the gate names the offending origin module and disposition |
| FR-007 | Layering proof | As a maintainer, I want a test that importing the capability module registers no `charter.activation` module and that its source imports nothing from `charter.activation` so that the "contract, not implementation" boundary is enforced rather than asserted. | High | Open | [build] | no — positive control proves the detector sees an activation import |
| FR-008 | No behavioural drift on the exotic families | As a maintainer, I want the capability read for a typeless mission and for a custom type declaring `requires_substantive_spec: true` pinned so that the seam cannot invent or default away a capability. | Medium | Open | [build] | no — the typeless case asserts `False`, the custom case asserts `True` on the same fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No hot-path regression | Reading the capabilities through the seam adds no layered-roster read: `resolve_mission_type_context` keeps its single roster read and the existing hot-path latency budget (already asserted by the mission-type performance test) still holds. | Performance | High | Open |
| NFR-002 | Offering stays activation-free | Importing `charter.offering.api` and every module it imports registers zero `charter.activation` entries in `sys.modules`, measured in a fresh subprocess. | Architecture | High | Open |
| NFR-003 | Seam shape stays reviewable | `charter.offering.api.__all__` stays sorted, duplicate-free and fully importable; the diff adds at most three symbols. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No offering → activation edge | The capability contract must be defined inside `charter.offering`; `charter.offering.*` must not import `charter.activation.*` (ADR 2026-10-16-1, Amendment 2026-10-19). | Technical | High | Open |
| C-002 | Exposure only | No change to the capability *semantics*: the resolution rules, the built-in defaults, the lazy thunks and the consumers' gates are untouched. Hardening (`run_dir` threading, the `except Exception` narrowing, `wp_driven` parity) is #6330; `code_producing` is #6327. | Scope | High | Open |
| C-003 | Amendment, not silent widening | Additive seam symbols are recorded in an ADR 2026-10-03-1 amendment (the #6541 precedent), and the seam keeps its disposition-coupled, facade-routed gate set. | Governance | High | Open |
| C-004 | Single authority | The value returned by the seam read is derived from the object's own capability attributes; no second copy of the built-in capability table is introduced. | Technical | High | Open |

### Key Entities

- **Mission-type capability contract**: the two boolean capabilities a resolved mission
  type answers — `wp_driven` (the type iterates work packages; its action sequence
  declares `implement`) and `requires_substantive_spec` (the type's authored rigour
  requirement, conservative `False` default).
- **Capability source**: anything that answers the two capability properties — in practice
  a resolved mission type.
- **Capability snapshot**: the immutable value object carrying the two answers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A test module whose only capability import is `charter.offering.api` reads both capabilities off a resolved `software-dev` mission type and asserts `(wp_driven, requires_substantive_spec) == (True, True)`; the same module asserts `research` → `(False, True)`, `documentation` → `(False, False)` and `plan` → `(False, False)`. — [build] · no-op passable: no
- **SC-002**: The offering public-surface, census and layering gate files pass with the new symbols present, and `charter.offering.api.__all__` grows by at most three entries. — [build] · no-op passable: no
- **SC-003**: Importing `charter.offering.api` in a fresh subprocess leaves `sys.modules` free of `charter.activation*` entries (current count 0), so the dependency direction is unchanged. — [ratchet] · no-op passable: no
- **SC-004**: Zero activation behaviour changes: the existing mission-type profile test suite passes unmodified. — [ratchet] · no-op passable: no
