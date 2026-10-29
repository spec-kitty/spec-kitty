# Mission Specification: Decision-significance adoption

**Mission Branch**: `issue-6445-decision-significance-adoption`
**Created**: 2026-10-27
**Status**: Draft
**Input**: Remediation mission M13 (operator brief, 2026-10-27): #6602, then #6445; #6446 left blocked (operator ruling, Decision Moment `01M5ZMPFCN3BFSEQ8VTN6MT3HF`).

## Intent Summary

- **Primary actor:** the mission runtime (`spec-kitty next`) when it scores an audit gate, resolves a step's RACI roles, or records a soft-gate decision. The reader is a maintainer or a downstream consumer of the shared event contract.
- **Trigger:** an audit step with a significance block is decided, a step is issued, or a medium-band decision is answered.
- **Desired outcome:** every significance and RACI record core writes is the shared `spec-kitty-events` model, validated by it, and names an actor for every role.
- **Rule that must always hold:** a RACI role that core cannot resolve to a concrete actor is recorded with the operator-ruled sentinel (`human-in-charge` for a human, `UNKNOWN` otherwise), never with an empty id. A role that the runtime inputs can resolve still resolves to that concrete actor.
- **Boundaries:** core consumes `spec-kitty-events` only as a published PyPI release through the lockfile. Persisting the decision timeout (#6446) is out of scope: it needs an EventBridge port door and a timeout trigger that do not exist yet.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Core runs on the current shared event contract (Priority: P1)

A maintainer installs Spec Kitty and gets the same `spec-kitty-events` release that core's CI tested, not a newer one that the open range happens to resolve.

**Why this priority**: the open range already resolves past the lock on a fresh install, so users run reducer and validator code core never tested. The other stories need the newer models.

**Independent Test**: resolve the lockfile and check the locked version, the compatibility manifest and the committed envelope snapshot agree; run the event consumer test directories green.

**Acceptance Scenarios**:

1. **Given** the lockfile, **When** the environment is synced, **Then** `spec-kitty-events` 11.3.0 is installed and the release-authority manifest names 11.3.0.
2. **Given** the committed envelope snapshots, **When** the envelope contract test runs, **Then** it finds a snapshot for the resolved version.

---

### User Story 2 - Significance records validate against the shared contract (Priority: P1)

When an audit gate is scored, the runtime writes a `SignificanceEvaluated` record built from the shared package model, so a consumer validating it with the package accepts it.

**Why this priority**: core's private copies can drift from the package; one model removes the drift by construction.

**Independent Test**: run an audit gate with a significance block through the runtime and validate the written record with the package's validator.

**Acceptance Scenarios**:

1. **Given** an audit step with a significance block, **When** the runtime decides it, **Then** the `SignificanceEvaluated` row in the run's event log validates with the package `SignificanceEvaluatedPayload`.
2. **Given** core's source tree, **When** it is searched, **Then** no local definition of the significance payload, timeout payload or resolved RACI snapshot models remains.

---

### User Story 3 - Every RACI role names an actor (Priority: P1)

When the runtime records a step's RACI roles or a soft-gate decision and cannot resolve an actor from its inputs, it records the sentinel the operator ruled instead of an empty id.

**Why this priority**: the shared package refuses a null or empty actor id, so without the mapping the adoption in Story 2 would refuse real records.

**Independent Test**: resolve RACI for prompt, advisory-audit and blocking-audit steps with and without the runtime inputs, and check every role (nested consulted and informed included) carries an id.

**Acceptance Scenarios**:

1. **Given** a step whose roles cannot be resolved from the inputs, **When** the runtime records its RACI, **Then** each human role reads `human-in-charge` and each llm or service role reads `UNKNOWN`.
2. **Given** a step whose inputs name the mission owner and the agent, **When** the runtime records its RACI, **Then** those concrete ids are recorded, not a sentinel.
3. **Given** a medium-band decision answered by an actor with no id, **When** the soft-gate decision is recorded, **Then** its actor carries the sentinel for its type.

### Edge Cases

- An explicit template RACI that leaves `actor_id` out: still accepted at load time and resolved from inputs as today.
- Consulted or informed roles that stay unresolved: recorded with the sentinel instead of a null id.
- Run snapshots and event logs written before this change keep their null ids. Nothing re-validates them on read (`decisions` is an untyped map and the run event log has no reader), so no migration is needed.
- The fail-closed escalation for an unresolvable responsible or accountable role inside `resolve_raci` is unchanged. The caller's fallback to the inferred binding resolves each role from the runtime inputs on its own and uses the sentinel only for the roles that stay unresolved (a known agent is recorded even when the mission owner is missing).
- A blank or whitespace-only template `actor_id` counts as missing and is resolved from the inputs; the package refuses an empty id.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Lock the shared event package at 11.3.0 | As a maintainer, I want the lock, the release-authority manifest and the envelope snapshot to name `spec-kitty-events` 11.3.0 so that installs run what CI tested (#6602). | High | Open | [build] | no |
| FR-002 | Raise the supported floor to 11.3.0 | As a maintainer, I want the declared range to start at the first published release that has the models and sentinels core imports so that an install cannot resolve a release without them. | High | Open | [build] | no |
| FR-003 | Use the package significance models | As a consumer of the event contract, I want core to build `SignificanceEvaluated` records, the timeout payload type and resolved RACI snapshots from the package models, with the local copies deleted, so that core cannot drift from the contract (#6445). | High | Open | [build] | no |
| FR-004 | Fill every RACI actor id | As a consumer of the event contract, I want every resolved or persisted RACI role, nested ones included, to carry an actor id, with an unresolved human mapped to `HUMAN_IN_CHARGE_ACTOR_ID` and an unresolved llm or service to `UNKNOWN_ACTOR_ID`, imported from the package, so that the package accepts every record (operator ruling on #6445). | High | Open | [build] | no — paired with the resolvable-inputs scenario on the same fixture |
| FR-005 | Keep input-based resolution | As a mission author, I want a template RACI without actor ids, and inferred roles, to keep resolving from the runtime inputs before any sentinel applies so that a known mission owner or agent is recorded (Decision Moment `01M5ZMPA58JS7K7S4S40CH7H1M`). | High | Open | [ratchet] | yes — paired with FR-004's unresolved scenario on the same fixture |
| FR-006 | Soft-gate actor carries an id | As a consumer of the event contract, I want the soft-gate decision's actor to carry the sentinel for its type when the answering actor has no id so that the record satisfies the package model. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Coverage of changed lines | At least 90% of changed lines are covered (the CI diff-cover gate). | Quality | High | Open |
| NFR-002 | Static checks | `ruff check`, `ruff format --check --force-exclude` and `mypy --strict` report zero issues on touched files, with no new `noqa` or `type: ignore`. | Quality | High | Open |
| NFR-003 | Complexity | No touched function exceeds cyclomatic complexity 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | PyPI-only consumption | `spec-kitty-events` is consumed only as a released PyPI version through `uv.lock`; no git pins or path overrides. | Technical | High | Open |
| C-002 | No new write path | No new Python event append path; the existing significance append is only re-typed. Persisting the decision timeout (#6446) is out of scope (ADR 2026-10-22-1). | Technical | High | Open |
| C-003 | Public imports only | Core imports only public `spec_kitty_events` symbols. | Technical | High | Open |
| C-004 | No overlap with mission M4 | The `specify_cli/decisions/` subsystem (#4848) is not modified. | Business | Medium | Open |

### Key Entities

- **RACI role binding**: an actor type (human, llm, service) and an actor id. The package model requires the id; an authoring-side binding in mission templates may omit it until resolution.
- **Resolved RACI snapshot**: a step's responsible, accountable, consulted and informed bindings with provenance (inferred rule or explicit override reason).
- **Significance record**: the scored significance, routing band and system actor of one audit-gate decision.
- **Actor-id sentinels**: `human-in-charge` (an inferred or unresolved human, the Human-in-Charge profile) and `UNKNOWN` (an unattributable llm or service).

## Assumptions

- The package's `ResolvedRaciSnapshot` provenance rules equal core's (three rules, verified against 11.3.0); only the error wording differs.
- Explicit consulted and informed humans that stay unresolved take `human-in-charge`, following the ruling's human row.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of `SignificanceEvaluated` records written by an audit-gate run validate with the shared package's validator. — [build] · no-op passable: no
- **SC-002**: 0 local definitions of the significance payload, timeout payload, resolved RACI snapshot or resolved role binding models remain in core. — [build] · no-op passable: no
- **SC-003**: 0 recorded RACI roles carry an empty or missing actor id across the prompt, advisory-audit and blocking-audit inference rules. — [build] · no-op passable: no
- **SC-004**: The event consumer test directories pass with the refreshed lock, with the counts recorded in the pull request. — [ratchet] · no-op passable: yes
