# Mission Specification: API-claimed and canceled WPs reach acceptance

**Mission Branch**: `kitty/mission-api-claim-accept-readiness-01M7X6Q6` (target `issue-5781-api-claim-accept-readiness`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: #5781 (P1, epic #5227), with #5818 and #7644 folded in (operator ruling 2026-11-20).

## Intent Summary

- **Primary actor**: an external orchestrator driving a Mission through `spec-kitty orchestrator-api`, and an operator closing a Mission with host `accept`.
- **Trigger**: a work package was claimed through the API (`start-implementation`, `transition --to claimed`), or with `agent status emit --to claimed`, or was canceled before anyone claimed it.
- **Desired outcome**: the Mission passes `accept` and `orchestrator-api accept-mission` exactly as a host-claimed twin does. A refusal that names a repair names one that works from the work package's current state.
- **Invariant**: the implementer of a work package is decided by one authority, `status/review_roles`, read from the event log. No implementer is fabricated for a work package that was never claimed.
- **Canonical terms**: Mission, work package (WP), implementer of record, claim sidecar (`policy_metadata` of the `planned -> claimed` event), acceptable ending.

Decision record: `decisions/DM-01M7X6R1QSXNTY0X64GQWWTZVZ.md` (the operator rulings).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An API-driven Mission can be accepted (Priority: P1)

An orchestrator claims WP01 with `orchestrator-api start-implementation --actor claude`, commits in the lane, submits, has `codex` review and approve, records the acceptance verdict, and calls `orchestrator-api accept-mission`.

**Why this priority**: the documented external-orchestrator loop cannot reach acceptance on its own output today (#5781, P1).

**Independent Test**: drive the API loop on a lanes Mission and on a coordination-topology Mission; `accept-mission` succeeds as it does for the host-claimed twin.

**Acceptance Scenarios**:

1. **Given** a Mission whose WPs were claimed through `start-implementation`, **When** `accept-mission` runs, **Then** it succeeds with no metadata issue.
2. **Given** the same Mission recorded by an older build (claim events without the `agent` sidecar), **When** host `accept` or `accept-mission` runs, **Then** no "missing agent" issue is raised; the implementer is read from the claim event's actor.
3. **Given** an API claim, **When** the snapshot is read, **Then** the `agent` slot holds the claiming `--actor`, as after a host claim.

### User Story 2 - A WP canceled before any claim is not asked for an implementer (Priority: P1)

The operator descopes WP02 from `planned` (host `move-task --to canceled --note`, with or without `--agent`, or `orchestrator-api transition --to canceled --note`).

**Why this priority**: today a Mission that mixes API and host verbs has no accept path once a WP is canceled before a claim.

**Independent Test**: each cancel variant, then host `accept` and `accept-mission`, on one fixture.

**Acceptance Scenarios**:

1. **Given** WP02 canceled from `planned` with an operator reason and no claim history, **When** host `accept` runs, **Then** no metadata issue names WP02 and WP02 appears under `canceled_wps`.
2. **Given** the same state, **When** `accept-mission` runs, **Then** WP02 is not in `incomplete_wps` and the Mission is accepted (#5818).
3. **Given** a synthetic cancellation (no operator reason), **When** `accept-mission` runs, **Then** it still refuses with that WP in `incomplete_wps`.

### User Story 3 - The repair hint works (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a WP with no recorded implementer in a state from which an implementing claim is legal, **When** accept refuses, **Then** the printed command, run as printed with a name substituted, records the implementer and clears the issue.
2. **Given** a WP with no recorded implementer in a state from which no implementing claim is legal (for example `done`, or a review lane), **When** accept refuses, **Then** no command is printed; the issue says why.

### User Story 4 - Rolling an API WP back to `planned` releases its claim (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an API-claimed WP, **When** `orchestrator-api transition --to planned` runs, **Then** the snapshot's `agent`, `shell_pid` and `shell_pid_created_at` slots are cleared, as `move-task --to planned` clears them.
2. **Given** that release, **When** a different implementer claims through the API or host `agent action implement`, **Then** the claim succeeds without `--force`.

### Edge Cases

- A WP canceled AFTER a claim keeps its implementer of record and passes the gate through it.
- An API claim records no `shell_pid` (there is no live shell); the claim sidecar omits the pid keys.
- The orchestrator `--policy` dictionary may not override the claim sidecar's `agent` key.
- A mixed Mission (API claim as one tool, a host move by another) now meets the move-task ownership guard, as a host-claimed WP does.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Gate reads the implementer of record | As an operator, I want the strict accept gate to read the implementer from `status/review_roles` (the event log), not the snapshot `agent` slot, so that API-claimed and older Missions pass without a migration. | High | Open | [build] | no — the API-claimed fixture refuses today |
| FR-002 | Canceled WP without claim history needs no implementer | As an operator, I want a canceled WP that was never claimed to raise no missing-implementer issue, and nothing to be stamped on it, so that descoping before a claim does not block acceptance. | High | Open | [build] | no — cancel variants P and V refuse today |
| FR-003 | Repair hint derived from the state machine | As an operator, I want the missing-implementer issue to name only a command that is legal from the WP's current lane and records an implementing claim, and to name none when no such command exists, so that the printed repair works. | High | Open | [build] | no — the hint prints `--to <current lane>` today |
| FR-004 | API claim records the agent through the shared builder | As an orchestrator, I want `start-implementation`, `transition --to claimed` and `agent status emit --to claimed` to record `agent` = the claiming actor through the one claim-sidecar builder, so that the snapshot and views show an owner and the ownership guard applies. | High | Open | [build] | no — the API claim records no agent today |
| FR-005 | accept-mission uses the acceptable-ending aggregate | As an orchestrator, I want `accept-mission` to decide incomplete WPs with the provenance-aware acceptable-ending authority, so that an operator-canceled WP is not incomplete (#5818). | Medium | Open | [build] | no — paired with the synthetic-cancel refusal on the same fixture |
| FR-006 | API move to planned releases the claim | As an orchestrator, I want `transition --to planned` to release the runtime claim through the same release authority `move-task` uses, so that another implementer can claim without force (#7644). | High | Open | [build] | no — the slots survive today |
| FR-007 | Contract version | As an API consumer, I want the orchestrator-api contract version raised by a minor step that names these behaviour changes. | Medium | Open | [build] | yes |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added status reads | The accept gate computes the implementer from the event stream it already reads: zero additional event-log reads per `collect_feature_summary` call. | Performance | Medium | Open |
| NFR-002 | Static checks | `ruff check`, `ruff format --check --force-exclude` and `mypy` report zero issues on every changed file; no new suppressions. | Maintainability | High | Open |
| NFR-003 | Coverage | Every new branch and helper is executed by a test in the same change (diff coverage at least 90%). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Core only | No change to `spec_kitty_events` reducer slot semantics (that needs a PyPI release). | Technical | High | Open |
| C-002 | Single authorities | The implementer is read only through `status/review_roles`; the claim sidecar is built only by the `status/emit` builder; the planned release is defined once in `status/`. | Technical | High | Open |
| C-003 | No fabrication | No implementer, agent or provenance is written for a WP that was never claimed. | Technical | High | Open |
| C-004 | Out of scope | #7752 (post-merge review lane check) and #5782 (accept-mission record commit) are not changed. | Business | Medium | Open |

### Key Entities

- **Implementer of record**: the identity `review_roles.latest_implementer_identity` derives from the WP's qualifying claim events.
- **Claim sidecar**: the `policy_metadata` of a `planned -> claimed` event; its `agent` key fills the snapshot `agent` slot.
- **Acceptable ending**: `approved`, `done`, or `canceled` with operator provenance (`status_lanes`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The #5781 reproducer exits 0 (API arm accepted) on lanes and coordination topologies. — [build] · no-op passable: no
- **SC-002**: The cancel-variant reproducer (arms X, P, V, control C) exits 0 for both host `accept` and `accept-mission`. — [build] · no-op passable: no
- **SC-003**: Every repair command the accept gate can print is executed by a test and clears the issue it names. — [build] · no-op passable: no
