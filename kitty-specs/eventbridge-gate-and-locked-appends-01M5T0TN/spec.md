# Mission Specification: EventBridge port, event-log writes gate and locked appends

**Mission Branch**: `issue-6603-6606-eventbridge-gate-and-locked-appends`
**Created**: 2026-10-25
**Status**: Draft
**Input**: User description: "EventBridge port skeleton plus a multi-log writes gate (#6603) and routing the unlocked event-log appends through one interim locked append primitive (#6606)."

## Intent Summary

**Confirmed from the operator brief and rulings (2026-10-25, #6117 comment; decisions `01M5T0VEWMHT2R9EC6WK6WXAHS`, `01M5T0VPQ9FD9CD7G846CPQGX5`).**

- **Primary actor:** a Spec Kitty maintainer who changes how the CLI records events, and every operator whose Mission writes event logs.
- **Trigger:** the CLI or runtime appends a row to an event log. That covers a work package transition, a run-journal entry, a decision answer, an Op record, an audit row, an archive record or a provenance row.
- **Desired outcome:**
  - every work package transition reaches the log through one EventBridge port;
  - every other event log is covered by a writes gate that names today's writers;
  - no event log is appended without the one interim ledger lock.
  This gives the Java write service (#6193) one door and one lock contract to take over.
- **Rule that must always hold:** an append either lands as whole lines, or it refuses and leaves the log byte-identical. It never extends a torn last line and never interleaves with another writer.
- **Boundaries:**
  - No live transport. The loopback HTTP client is #6675.
  - No new Python-side validation authority, because the service will be authoritative.
  - No change to row bytes, file locations or reducer behaviour.
  - The interim locked appends retire at the #6193 handover and are marked so.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A work package transition goes through the EventBridge port (Priority: P1)

A maintainer moves a work package. The CLI builds the transition exactly as today, then hands it to the EventBridge port instead of calling the append primitive directly. Without a bound adapter, the local file adapter writes the same bytes to the same log.

**Why this priority**: ADR 2026-10-14-1 D-2 and ADR 2026-10-22-1 step 0 make the port the first step of the migration. Every later step, including the Java client, plugs in here.

**Independent Test**: Bind a recording test adapter, move a work package through each door (the flat shell and the coordination transaction), and observe one port call per transition, carrying the rows and the resolved write location. Unbind it, and the log bytes match the pre-change bytes.

**Acceptance Scenarios**:

1. **Given** no adapter is bound, **When** a work package transitions through either door, **Then** the log gains the same rows, byte for byte, as before this Mission.
2. **Given** a recording adapter is bound, **When** a work package transitions, **Then** the adapter receives exactly one call with the transition and its annotation as one unit, and nothing is written by any other path.
3. **Given** the domain code that calls the port, **When** its imports are inspected, **Then** it depends only on the port, not on the store's append primitives.

---

### User Story 2 - A new event-log writer fails the writes gate (Priority: P1)

A contributor adds code that appends to `run.events.jsonl`, `decisions.events.jsonl`, a `kitty-ops/` log or any other event log the ADR's Confirmation names, without going through a sanctioned door. The architectural gate fails and names the file, the function and the log.

**Why this priority**: ADR Confirmation G-2. Without a gate, the writer census decays silently, which is how the unlocked appends grew.

**Independent Test**: Feed the gate a synthetic module that appends to each named log. Each is reported. Run it on the real tree, and it is green with today's writers ledgered.

**Acceptance Scenarios**:

1. **Given** today's tree, **When** the gate runs, **Then** it passes, and every ledgered writer is still live.
2. **Given** a new raw append to any named log, **When** the gate runs, **Then** it fails and names the site.
3. **Given** a new caller of the locked append door, **When** the gate runs, **Then** it fails until the caller is ledgered with a reason.

---

### User Story 3 - Concurrent or crashed appends never corrupt an event log (Priority: P1)

Two processes, or a background thread and the main thread, append to the same log at once, or an earlier write was cut short. Each append holds the interim ledger lock and writes its lines in one write. A torn last line is refused with a named error and a remedy, so it is not extended into a corrupt row that could be committed and travel to other clones.

**Why this priority**: #6606. `decisions.events.jsonl` is committed and carried by a merge driver, so a torn line spreads.

**Independent Test**: Append to a log that ends without a newline. The append refuses, and the file is byte-identical. Append from several processes at once, and every line is whole.

**Acceptance Scenarios**:

1. **Given** a log whose last byte is not a newline, **When** any routed writer appends, **Then** the append refuses with the torn-tail error and the file is unchanged.
2. **Given** many concurrent appenders to one log, **When** they finish, **Then** every line parses and no line is lost or interleaved.
3. **Given** the lock is held past the bounded wait, **When** a writer appends, **Then** it refuses with the lock-timeout error, and nothing is written.

### Edge Cases

- **Not a git repository** (an ad-hoc directory): the lock file falls back to a sibling of the log, and the append still locks.
- **Log does not exist yet:** it is created with its parent directory, as today. Op-record appends that require an existing file keep refusing a missing one.
- **A caller swallows failures today** (decision log, Mission v1 events, propagation errors, the Op index): a refusal is swallowed the same way, because the new errors are I/O errors.
- **The Op record's identity check:** it runs under the same lock as its append, so an identity check and an append cannot be split by another writer.
- **A final symlink at a log path:** the Op-record appends keep refusing it (no-follow).

## Domain Language

- **EventBridge port:** the domain-owned interface through which the domain records facts, grown from `RuntimeEventEmitter`. Do not call it "the writer": the writer is an adapter behind it.
- **Interim ledger lock:** the one exclusive lock contract every event-log append takes until the #6193 handover. Not "the status lock" (`feature_status_lock`), which stays the status log's own.
- **Torn tail:** a log whose last byte is not a newline.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | EventBridge port | As a maintainer, I want an EventBridge port grown from `RuntimeEventEmitter` (Mission state advance entry points plus a work package transition entry point) so that the domain depends on one interface, not on the writer. | High | Open | [build] | no — a test adapter must satisfy the port type and be reachable through the binding |
| FR-002 | Both transition doors go through the port | As a maintainer, I want `_persist_prepared` (flat shell) and `BookkeepingTransaction.append_events` (coordination shell) to hand their durability unit to the port so that the transition has one entry point. | High | Open | [build] | no — a bound recording adapter must observe the call from each door |
| FR-003 | Local file adapter keeps today's bytes | As an operator, I want the default adapter to write through today's store primitives so that logs, ordering and reducer outcomes are unchanged. | High | Open | [ratchet] | yes — paired with FR-002's recording-adapter control on the same fixture |
| FR-004 | Binding at the composition root | As a maintainer, I want an adapter to be bindable once (reject-on-conflict, like the emitter registry) and resettable in tests so that the Java client (#6675) can plug in later without a second seam. | Medium | Open | [build] | no — a conflicting second binding must raise |
| FR-005 | Multi-log writes gate | As a maintainer, I want an architectural gate over every event log the ADR Confirmation names (run journal, decisions, Mission events, `kitty-ops/*.jsonl`, `canonical-events.jsonl`, glossary logs) plus the other G-5 logs, frozen at today's writers, so that a new writer fails. | High | Open | [build] | no — synthetic writers for each log must be reported |
| FR-006 | Gate non-vacuity | As a maintainer, I want the gate to fail when it finds no writers, or when a ledger entry is stale, so that it cannot pass by matching nothing. | High | Open | [build] | no — the floor tests are fed to the same scanner |
| FR-007 | One interim locked append primitive | As an operator, I want one append primitive that takes the interim ledger lock, refuses a torn tail, writes the unit in one `O_APPEND` write and fsyncs it, so that no append interleaves or extends a torn line. | High | Open | [build] | no — torn-tail and concurrency tests fail without it |
| FR-008 | Route the eight unlocked appends | As an operator, I want the Op lifecycle, propagation-error, decision log, Mission v1 events, run journal, policy audit, archive registry and encoding provenance appends to go through the primitive, each keeping its row bytes. | High | Open | [build] | no — each writer's torn-tail refusal test fails before routing |
| FR-009 | Route the Op-record appends | As an operator, I want the `kitty-ops` index, closure spine and per-Op appends (`invocation/writer.py`) to take the same lock, with the identity check under the lock, so that one lock contract covers every append. | High | Open | [build] | no — torn-tail and lock tests fail before routing |
| FR-010 | Lock the glossary contract append | As an operator, I want the glossary's contract-writer append (`persistence.append_event`) to run under the same lock so that its advisory torn-tail check is no longer racy. | Medium | Open | [build] | no — a lock-held test observes the append waiting |
| FR-011 | Mark the interim surface | As a maintainer, I want each interim locked append and the primitive marked as retiring at the #6193 handover so that the Java handover deletes them, rather than keeping a second writer. | Medium | Open | [build] | no — the gate ledger names #6193 for every routed caller |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte stability | 100% of rows written by the routed writers are byte-identical (content and key order) to the rows written before this Mission, for the same input. The only exception is line endings on Windows, which become LF. | Compatibility | High | Open |
| NFR-002 | Concurrency safety | With 8 concurrent appenders × 50 rows each to one log, 400 of 400 lines parse and none is interleaved. | Reliability | High | Open |
| NFR-003 | Bounded wait | A writer waits at most 10 s for the lock, then refuses with a named error code. | Reliability | Medium | Open |
| NFR-004 | Gate speed | The new gate runs in under 5 s on the full `src/` tree. | Developer experience | Medium | Open |

### Constraints

| ID | Title | Constraint | Rationale | Priority | Status |
|----|-------|------------|-----------|----------|--------|
| C-001 | No live transport | The port ships with the local file adapter only; no HTTP or socket client. | #6675 owns the transport. | High | Open |
| C-002 | No new validation authority | The primitive validates line framing only, not row content; no writer gains strict schema validation. | Operator ruling 2026-10-25: the Java service is authoritative for validation. | High | Open |
| C-003 | One lock contract | Every routed append uses the same lock-path rule, a per-log lock file under `<git-common-dir>/spec-kitty-locks/`, with `flock(2)` semantics through `kernel.locks`. | #6193 must interoperate with one contract. | High | Open |
| C-004 | Layer direction | The port lives in `runtime`; the adapter and primitive callers live in `specify_cli`; the primitive lives in `kernel`. No new layer-ledger entry. | Enforced chain `kernel <- charter <- runtime <- specify_cli`. | High | Open |
| C-005 | Status log unchanged | `status.events.jsonl` keeps its own gate, lock and primitives. | The status log is the sole lane authority; its durability path is out of scope. | High | Open |

### Key Entities

- **Work package transition (port input):** the rows of one durability unit (a transition and its annotation), plus the resolved write location and contract.
- **Ledger append unit:** one or more whole lines that land together under the lock.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001:** 0 unlocked plain appends to any named event log remain in `src/`, checked by the writes gate. — [build] · no-op passable: no
- **SC-002:** both work package transition doors reach the log only through the port, shown by a recording adapter in 2 of 2 doors. — [build] · no-op passable: no
- **SC-003:** a torn tail is refused by 100% of the routed writers, and the file stays byte-identical. — [build] · no-op passable: no
- **SC-004:** existing status, decisions, runtime, invocation and consolidation suites pass unchanged. — [ratchet] · no-op passable: yes — paired with SC-002 and SC-003

## Assumptions

- `kernel.git_topology.git_common_dir` is the canonical resolver for the lock directory, as for the status lock.
- Callers that swallow I/O errors today may keep doing so. Making those failures loud is a later step (ADR 2026-10-14-1 "What must stay true": recorded, rerunnable consumer failures).
- The service validates at handover. Until then, each writer keeps its own row shape.

## Out of Scope

- Retiring the lifecycle modules (D-4; #6185, #6438) and moving side effects into consumers (D-5).
- The decision-point rows in `status.events.jsonl` (#6412).
- The transport (#6675) and the Java write side (#6193).
