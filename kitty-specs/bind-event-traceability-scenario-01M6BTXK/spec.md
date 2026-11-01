# Mission Specification: Bind the event-traceability acceptance scenario

**Mission Branch**: `issue-6260-bind-event-traceability-scenario`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue #6260 — bind the drafted `@wip` acceptance scenarios in
`tests/scenarios/status/event-traceability.feature` and remove the `@wip` tags. Child of #6133;
refs #6137, #4941. Guidance from the issue: reuse the shipped `MissionFixture`/`MissionLifecycle`
builders, add only concrete missing primitives, add a positive control, and leave the
`@promise:<id>` assignment to QA.

## Intent Summary

A QA-drafted scenario states a user-facing promise: **the last decision recorded on a work package
is the one that counts** — a rejection recorded after an approval sends the work package back for
rework, and a Mission whose work package was rejected after that approval is refused at
consolidation, even when one reviewer's clock runs ahead of another's. The behaviour is already
guarded by `tests/consolidation/test_wall_clock_claim_p0_repro.py` (the #4941 fix); the scenario is
its customer-facing description.

The scenario is drafted but unbound, so it runs only in the non-gating `@wip` pass. This Mission
binds its steps, adds a same-fixture positive control, and removes `@wip` so it joins the gating
nightly. It changes no product behaviour.

- **Primary actor**: a Spec Kitty user running a Mission with reviewers, whose latest recorded
  decision must win.
- **Trigger**: a reviewer records a rejection of a work package that is already approved, and the
  user then consolidates the Mission.
- **Outcome**: the scenario's steps are bound to the real CLI, the work package is sent back, and
  consolidation is refused for that work package — on the clock-skewed arrangement as well.
- **Rule that must always hold**: the promise is checked through the CLI's real entry points; no
  assertion is deleted, softened, or made vacuous to obtain a green run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A late rejection sends the work package back (Priority: P1)

A reviewer rejects a work package that a colleague approved from a machine whose clock runs ahead.
The rejection is the last decision, so the work package returns to rework and is no longer reported
as approved.

**Why this priority**: this is the promise the scenario exists to describe; without it the
consolidation scenario below has no observable precondition.

**Independent Test**: the first scenario in `tests/scenarios/status/event-traceability.feature`
runs green through the acceptance-jvm runner once its steps are bound.

**Acceptance Scenarios**:

1. **Given** a Mission whose work package "WP01" has been approved, **When** a reviewer records a
   rejection of "WP01" after that approval, **Then** "WP01" is sent back for rework and is not
   reported as approved.

### User Story 2 - A Mission containing that work package is refused at consolidation (Priority: P1)

The user consolidates the Mission. Because a work package that was approved has since been
rejected, consolidation refuses and names that work package; no rejected content lands on the
target branch.

**Why this priority**: this is the harm the promise prevents — rejected content silently landing.

**Independent Test**: the second scenario in the same feature file runs green through the
acceptance-jvm runner once its steps are bound.

**Acceptance Scenarios**:

1. **Given** a Mission whose work package "WP01" has been approved and a reviewer has recorded a
   rejection of "WP01" after that approval, **When** I consolidate the Mission, **Then**
   consolidation is refused because "WP01" is not approved.

### User Story 3 - The binding proves its own fixture (Priority: P2)

A maintainer can see that the bound scenarios are not passing vacuously: the same fixture, with the
last decision left as the approval, consolidates successfully.

**Why this priority**: without a positive control, a scenario whose arrange or act silently did
nothing could still pass its refusal assertions.

**Independent Test**: the positive-control scenario in the same feature file consolidates a Mission
whose only recorded decision is the approval and succeeds.

**Acceptance Scenarios**:

1. **Given** a Mission whose work package "WP01" has been approved and accepted, **When** I
   consolidate the Mission, **Then** the command succeeds and the work package's work lands on the
   target branch.

### Edge Cases

- A rejection recorded on the same clock as the approval (no skew) must also send the work package
  back; the skewed arrangement is the harder case, not a replacement for the ordinary one.
- The rejection must be recorded through `spec-kitty agent status emit`, not by editing the status
  log, so the CLI's real guard decides the outcome.
- If the CLI refuses the out-of-order rejection with a diagnostic instead, the scenario fails rather
  than silently accepting either outcome: the scenario asserts the rework lane, and a refusal is
  reported as a product finding rather than papered over.
- The crafted approval row must be the only non-CLI write; every other fixture write stays within
  the builders' documented allowance.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Approved work-package arrange | As QA, I want a bound Arrange step that builds a Mission with a work package already approved, so that both scenarios start from the promised state. | High | Open | [build] | no |
| FR-002 | Clock-skewed approval arrangement | As QA, I want the arrange to restamp the approval row with a future `at` as a teammate's pull would deliver it, so that the scenario exercises the out-of-order case. | High | Open | [build] | no |
| FR-003 | Rejection act through the CLI | As QA, I want a bound Act step that records the rejection through `spec-kitty agent status emit`, so that the CLI's own guard is what decides the outcome. | High | Open | [build] | no |
| FR-004 | Rework and approval assertions | As QA, I want assertions that the work package is in the rework lane and not reported as approved, so that the promise is checked positively, not by absence of output. | High | Open | [build] | no |
| FR-005 | Consolidation refusal | As QA, I want a bound Act/Assert pair that consolidates the Mission and requires the refusal to name the rejected work package, so that the harm is described end to end. | High | Open | [build] | no |
| FR-006 | Same-fixture positive control | As a maintainer, I want a positive-control scenario that consolidates the same fixture when the approval is the last decision, so that the refusal cannot pass vacuously. | High | Open | [build] | no |
| FR-007 | Remove the @wip tags | As a maintainer, I want `@wip`, `@wip-owner` and `@wip-since` removed, so that the scenario joins the gating nightly. | High | Open | [build] | no |
| FR-008 | Per-PR scenario contract stays green | As a maintainer, I want `tests/architectural/test_scenario_contract.py` to report no unbound or ambiguous steps, so that the bound vocabulary is proven before the nightly runs. | High | Open | [ratchet] | no |
| FR-009 | Changelog and docs | As a maintainer, I want the `[Unreleased]` changelog entry and the affected testing docs updated, so that the user-visible change is recorded. | Medium | Open | [build] | no |

**FR-002 note**: the approval row is restamped without `lamport_clock`, exactly as the CLI writes
lane transitions, and the restamp is the single write outside the builders' allowance documented in
ADR 2026-10-15-1 decision 6. The scenario's maintainer notes state that exception and why.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Deterministic skew | The crafted approval stamp is the emitter's real current time plus a fixed ten-minute offset, so the arrangement never depends on a passing wall-clock moment. | Reliability | High | Open |
| NFR-002 | Nightly runtime | Each bound scenario completes inside the nightly leg's existing per-scenario budget; no added sleep or retry. | Performance | Medium | Open |
| NFR-003 | No retries, no flakes | The binding adds no retry and no timing-dependent wait; a flake is reported as a defect, per the repository's flakiness policy. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never weaken the promise | Assertions in the drafted scenario are only added to, never deleted or softened; removing `@wip` is earned by a genuine pass. | Process | High | Open |
| C-002 | No invented promise id | The `@promise:<id>` tag is assigned by QA from the promise registry; this Mission does not invent one and records the pending assignment on the issue and in the PR. | Process | High | Open |
| C-003 | Step vocabulary is canonical | New steps live in `acceptance-jvm/` with Arrange/Act/Assert placement, and the scenario reuses shipped builders before adding a primitive. | Technical | High | Open |
| C-004 | No product behaviour change | The #4941 fix and its pytest guard are untouched; this Mission binds a description of shipped behaviour. | Technical | High | Open |

### Key Entities

- **Acceptance scenario**: a Gherkin behaviour description under `tests/scenarios/`, tagged for the
  gating nightly once bound.
- **Step definition**: a Cucumber-JVM method in `acceptance-jvm/`, one of Arrange, Assume, Act or
  Assert.
- **Status event row**: one line of `status.events.jsonl`; the crafted approval row carries a future
  `at` and no `lamport_clock`.
- **Mission fixture**: the black-box CLI+git builders that plan a Mission and walk a work package
  through its lanes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Both scenarios in `tests/scenarios/status/event-traceability.feature` run green in the acceptance-jvm runner with no `@wip` tag left — [build] · no-op passable: no
- **SC-002**: The same-fixture positive control consolidates a fully approved, accepted Mission successfully in the same runner run — [build] · no-op passable: no
- **SC-003**: `tests/architectural/test_scenario_contract.py` reports zero errors and zero unbound steps for the feature file — [ratchet] · no-op passable: no
- **SC-004**: The changed behaviour description keeps every drafted assertion and adds at least the positive control, verified by reading the diff — [build] · no-op passable: no
