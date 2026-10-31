# Mission Specification: Optional Lamport clock consumer audit

**Mission Branch**: `issue-6414-optional-lamport-clock-consumer-audit`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6414 — "Audit core consumers of Event.lamport_clock and status_event_sort_key for events 11.0 (optional clock, 4-tuple key)".
Guidance from the operator: cite #6798/#6801/#6816/#5927 in the PR's `## Deferred` section; never merge, never arm auto-merge, never push `main`; the PR must actually solve the issue rather than restate it.

## Problem

`spec-kitty-events` 11.0.0 (spec-kitty/spec-kitty-events#120/#128, consumed here since `spec-kitty#6399` / PR #6425 and pinned at `>=11.3.0,<12`) made two breaking changes that core code can silently mishandle:

1. `Event.lamport_clock` is now `Optional[int]`. An envelope without it is **unclocked** and orders *before* every clocked envelope (`spec_kitty_events.ordering.canonical_order_key` = `(1 if clocked else 0, clock or 0, utc_timestamp_iso, event_id)`). `merge` rejects unclocked events and `work_replay` refuses them.
2. `status_event_sort_key` returns a **4-tuple** (it now delegates to `canonical_order_key`) instead of a 3-tuple.

Any core code that reads `lamport_clock` as a required `int`, unpacks or compares that key as a 3-tuple, or feeds unclocked envelopes into `merge`/`work_replay` is broken. Any core code that *writes* a synthetic `lamport_clock` where the row never recorded a clock is asserting a causal position the row cannot support — under the new contract the honest representation is `null` (unclocked), not `0` (clocked at position zero).

The 2026-10-19 triage on the issue recorded a static-only pass ("no `status_event_sort_key` callers in `src/`") and the 2026-10-27 remediation slicing parked the *direction* (#6609, Lamport-primary ordering) as post-GA. Neither replaced the acceptance deliverable: a per-consumer audit with evidence, and mixed clocked/unclocked coverage where a core path actually consumes such a stream. That deliverable is this mission.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer can read the audit and trust it (Priority: P1)

A maintainer landing the events 11.x line opens one repository document and sees every core site that touches `lamport_clock` or the ordering keys, what each one does with a `None` clock or the 4-tuple key, and which test pins that verdict.

**Why this priority**: The issue's first acceptance criterion is that findings are recorded and every consumer is either made `None`/4-tuple safe or shown unaffected. Evidence in a test, not prose in an issue comment, is what stops the next reader from re-running the same audit.

**Independent Test**: Read the audit document; every row names a source path, a verdict, and a test that fails if the verdict stops being true.

**Acceptance Scenarios**:

1. **Given** the audit document, **When** a reader follows any row's proof test, **Then** running that test exercises the named core path and passes.
2. **Given** a new core consumer of `lamport_clock` appears, **When** the audit's inventory test runs, **Then** it fails and names the unlisted path (the inventory is not silently stale).

---

### User Story 2 - The upgrade migration stops asserting a fake clock (Priority: P1)

An operator upgrading a project that still has legacy 9-key lifecycle envelopes gets rows that are honestly marked unclocked (`lamport_clock: null`) instead of clocked at position `0`.

**Why this priority**: This is the one real defect the audit finds. `canonical_order_key` places a clocked row after every unclocked one, so a migrated legacy row currently sorts after strictly newer, never-migrated rows in the same log — an order inversion the row itself never justified. It also groups every migrated row into one "concurrent" bucket for any consumer that groups by `(wp_id, lamport_clock)`.

**Independent Test**: Run the upgrade migration over a log containing a legacy row and a later fresh unclocked row; the migrated row is unclocked and still sorts before the newer row.

**Acceptance Scenarios**:

1. **Given** a legacy 9-key envelope row, **When** the migration rewrites it, **Then** the migrated row carries `lamport_clock: null` and remains valid under `spec_kitty_events.Event`.
2. **Given** a log with a migrated legacy row stamped earlier than a fresh unclocked row, **When** both are ordered with `canonical_order_key`, **Then** the earlier-stamped row still sorts first.
3. **Given** an already-migrated file (any sentinel value), **When** the migration re-runs, **Then** it is a byte-identical no-op (idempotency preserved).

---

### User Story 3 - A mixed clocked/unclocked stream is provably safe where it is read (Priority: P2)

An operator whose mission log mixes clocked envelopes (imported or hand-written) with the CLI's own unclocked rows gets the same reduced lane state, with no exception, from every core read path.

**Why this priority**: The issue's second acceptance criterion. The read path is the only place a mixed stream can actually reach core; proving it is what turns "no callers found" into "no callers found *and* the readers that do see these rows are clock-agnostic".

**Independent Test**: Feed a fixture stream, then the same stream with `lamport_clock` added to alternating rows, through the CLI's snapshot materialization; assert an identical result.

**Acceptance Scenarios**:

1. **Given** a status event log, **When** alternating rows gain a `lamport_clock`, **Then** `materialize` produces a byte-identical `status.json` to the clock-free log.
2. **Given** the same mixed stream, **When** the events-package Lamport-ordered reducer (`reduce_status_events`, the only 4-tuple/`lamport_clock` consumer in the dependency) reduces it, **Then** it returns a result instead of raising, and its output is deterministic across permutations.
3. **Given** a source mission whose rows carry a clock, **When** the TeamSpace dry-run synthesizes replay envelopes, **Then** each emitted envelope is clocked with a strictly increasing index in `(at, event_id)` order, i.e. the source clock is discarded rather than mixed.

---

### Edge Cases

- A row that carries `lamport_clock: null` explicitly (not absent) — must be treated as unclocked, not as a missing key error.
- A row that carries `lamport_clock: 0` — clocked at zero, which the audit must distinguish from unclocked; the migration must not produce it.
- A migrated log that already contains `lamport_clock: 0` from an older migration run — the re-run must stay a no-op rather than rewrite payload-bearing rows.
- A `StatusEvent` row with an extra `lamport_clock` key — the CLI reader must not reject it and must not promote it into a core ordering signal.
- An empty log, and a log where every row is unclocked — both must reduce to the same state as before this change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record the consumer audit | As a maintainer, I want one document listing every core consumer of `Event.lamport_clock` and the events ordering keys with a verdict each, so that the issue's findings survive the issue thread. | High | Open | [build] | no |
| FR-002 | Pin the inventory against drift | As a maintainer, I want a test that fails when a core module starts referencing `lamport_clock`/`status_event_sort_key`/`canonical_order_key`/`node_order_key`/`merge`/`work_replay` without being listed, so that the audit cannot silently go stale. | Medium | Open | [ratchet] | no |
| FR-003 | Migration emits an unclocked row | As an operator, I want the lifecycle-envelope migration to write `lamport_clock: null` for a row that never recorded a clock, so that the row does not claim a causal position it never had. | High | Open | [build] | no |
| FR-004 | Migration stays idempotent | As an operator, I want a re-run over an already-migrated file to be a byte-identical no-op, so that upgrading twice changes nothing. | High | Open | [ratchet] | no |
| FR-005 | Mixed stream through the CLI read path | As an operator, I want a mission log that mixes clocked and unclocked rows to materialize to exactly the same snapshot as the clock-free log, so that the optional clock cannot change lane state. | High | Open | [build] | no |
| FR-006 | Mixed stream through the Lamport-ordered reducer | As an operator, I want the dependency's 4-tuple/Lamport reducer to accept a mixed stream deterministically, so that any future core adoption of it cannot crash on a CLI-written log. | Medium | Open | [build] | no |
| FR-007 | Dry-run normalizes the source clock | As a maintainer, I want the TeamSpace dry-run to emit clocked envelopes indexed in `(at, event_id)` order regardless of any clock on the source rows, so that synthesized replay order stays the wall-clock order it claims. | Medium | Open | [ratchet] | no |
| FR-008 | Correct the issue's ordering direction claim | As a reader, I want the audit to state the actual ordering direction (unclocked sorts *before* clocked) and cite the contract, so that the record does not propagate the inverted claim from the issue body. | Low | Open | [folded] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new runtime dependency | The audit and fixtures use only the already-pinned `spec-kitty-events>=11.3.0,<12`; no new import, no version bump. | Compatibility | High | Open |
| NFR-002 | No behaviour change outside the migration sentinel | Every other core path produces byte-identical output for its existing fixtures (the CLI's lane readers keep their wall-clock `(at, event_id)` fold); only the migration's `lamport_clock` sentinel changes. | Reliability | High | Open |
| NFR-003 | Fast-tier tests only | The added tests run in the `fast` tier (plus the migration suite's existing marks) and add under 5 seconds to their shard; no heavy suite is run locally. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Status ordering direction is out of scope | #6609 (Lamport-primary ordering for the status log) is parked post-GA. This mission audits and fixes conformance; it does not re-order lane state by Lamport. | Technical | High | Open |
| C-002 | Single canonical authority | The ordering key stays `spec_kitty_events.ordering.canonical_order_key`; core must not re-implement it, and the migration must use the dependency's unclocked representation (`None`) rather than inventing a sentinel. | Technical | High | Open |
| C-003 | Issue-matrix completeness | The mission carries exactly one issue row (#6414); the verdict is terminal before the PR is flipped. | Process | Medium | Open |

### Key Entities

- **Lifecycle envelope row**: one JSONL line in `<mission>/status.events.jsonl` or `.kittify/canonical-events.jsonl` carrying `event_type`/`payload`. Legacy rows are 9-key (`schema_version: "5.0.0"`); the migration rewrites them to the strict 14-key shape.
- **Status event row**: one lane transition, read into `StatusEvent`. It carries no `lamport_clock` on the wire as the CLI writes it; a foreign row may add one.
- **Ordering key**: `(clocked_flag, clock_or_zero, utc_timestamp_iso, event_id)` — the dependency's single authority for mixed-stream ordering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every core reference to `lamport_clock`, `status_event_sort_key`, `canonical_order_key`, `node_order_key`, `total_order_key`, `merge` and `work_replay` appears in the audit document with a verdict and a proof, and the inventory test fails when a new one is added without a row — [ratchet] · no-op passable: no
- **SC-002**: 0 migrated legacy rows carry a non-`None` `lamport_clock` after one migration pass, and the re-run produces a byte-identical file (existing idempotency assertion still holds) — [build] · no-op passable: no
- **SC-003**: A mixed clocked/unclocked stream materializes to a `status.json` byte-identical to the same stream without clocks, on the shipped replay fixtures — [build] · no-op passable: no
- **SC-004**: 0 unexplained exceptions from the dependency's Lamport-ordered reducer on a mixed stream; the result is identical across two permutations of the input — [build] · no-op passable: no
- **SC-005**: The issue row for #6414 reaches a terminal verdict (`fixed`) with a changelog entry and a PR that cites it — [folded] · no-op passable: no
