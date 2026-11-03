# Mission Specification: Gated in_review rewind

**Mission Branch**: `issue-7080-gated-in-review-rewind`
**Created**: 2026-11-03
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#7080 — `in_review -> in_progress` still records a wire-invalid rewind. The pinned `spec_kitty_events` contract gates three rewinds to `in_progress` (`for_review`, `in_review`, `approved`) on a non-empty `review_ref` whether or not the event is forced; the local rule the writer and the auditor read, `status/wp_state.py::REVIEW_REF_REQUIRED_EDGES`, omits `in_review -> in_progress`. #6955 gated the `approved` edge and filed this follow-up because this edge's evidence is a structured `review_result` the status emit path never turns into a `review_ref`, so gating it alone would refuse legitimate writes. Ground it, fix it red-first (thread the pointer, then gate the edge), changelog fragment, draft PR, never merge."

## Problem Statement

A work package rejected in review can be sent back to `in_progress` with a pointerless status
event that hosted sync rejects.

Reproduced on `main` @ `d18c4f1d58` through the exact probe in the issue:

```
requires_review_ref("in_review", "in_progress")                    -> False
wp_state_for("in_review").check_transition(IN_PROGRESS,
    GuardContext(force=True, actor="codex", reason="needle"))      -> (True, None)   # appended
validate_transition(StatusTransitionPayload(..., review_ref=None,
    force=True, reason="needle")).valid                            -> False          # rejected on sync
```

The vendored contract (`spec_kitty_events.status`, "Review-Ref-Gated Rewind Family") gates
three rewinds to `in_progress` on a non-empty `review_ref` — `for_review`, `in_review` and
`approved` — and states the requirement holds "whether the event is forced or not". The local
set holds only `for_review -> in_progress` on this base (`approved -> in_progress` is gated by
#6955 in PR #7102, which is open and not yet merged). The `in_review` edge is therefore
locally accepted and locally audited clean while the shared contract the sync consumer
enforces rejects it: the #3307 silent-sync-rejection class, still open on this edge.

### Why the two halves must land together

#6955 deliberately left this edge out. The evidence a caller supplies for an `in_review` exit
is a **structured** `review_result` (`--review-result-json` on `agent status emit`, or
`TransitionRequest.review_result` from any direct caller). `prepare_transition` passes that to
the guard as `GuardContext.review_result` and records it on the event, but it never threads
`review_result.reference` into the event's `review_ref`. Adding the edge to
`REVIEW_REF_REQUIRED_EDGES` first would refuse those legitimate writes.

`move-task` already threads it: `tasks_transition_core.build_transition_plan` copies
`review_result.reference` onto `emit_review_ref` when the caller supplied no pointer (#3307).
The generic emit doors (`agent status emit`, `orchestrator-api wp transition`, direct
`emit_status_transition` callers) do not. This mission mirrors that rule in
`prepare_transition` — the tree's single validation and event-build authority — and then gates
the edge, so the writer refuses a pointerless row *before* the append and the auditor reports
a stored one.

### The pin this mission inherits, and what happens to it

#6955 could not gate this edge, so its tests pinned the edge as **still admitted**:
`test_force_elsewhere_is_unchanged` and `test_requires_review_ref_excludes_every_other_edge`
both enumerate `("in_review", "in_progress")` as outside the set. The pin's intent is that the
deferral cannot silently flip — either direction. This mission closes the deferral, so it must
flip that pin **deliberately and visibly**, and keep the intent for what remains:

- the two exclusion entries naming `in_review -> in_progress` are removed with a comment that
  says why they moved, and the edge moves to the positive (`covers`) pin;
- the ratchet becomes merge-order independent: every local member must be a real contract
  requirement (proven on the pinned dependency in both directions), and the local set must be a
  subset of the contract's gated family. It deliberately does **not** assert an exact set, so
  #7102 (`approved`) and this mission cannot make each other's pin false whichever lands first;
- no assertion about the `approved` edge is added or removed here; that edge and its pin stay
  #6955/#7102's.

Scope boundary: this mission fixes one edge's pointer derivation and gate. It does not re-pin
`spec-kitty-events`, does not add a new sentinel, does not change the force-provenance rule,
does not rewrite historical rows, and does not take over the `approved` edge.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A rework rewind from in_review records an event hosted sync accepts (Priority: P1)

A reviewer rejects a work package in `in_review` with a `changes_requested` review result whose
`reference` points at the feedback. The event recorded when the package goes back to
`in_progress` must carry that reference on the wire, so the rework propagates instead of being
silently dropped at sync.

**Why this priority**: This is the reported defect and the reason the issue is open.

**Independent Test**: On a mission whose WP01 sits in `in_review`, run
`agent status emit WP01 --to in_progress --review-result-json '{"reviewer": ..., "verdict":
"changes_requested", "reference": "review-cycle://WP01/1"}'` through the real CLI, read the last
`status.events.jsonl` row, and assert `review_ref == "review-cycle://WP01/1"`; rebuild that row
as a `spec_kitty_events.status.StatusTransitionPayload` and assert
`validate_transition(...).valid is True`. On the pre-fix tree the same row records
`review_ref: null` and the payload is invalid.

**Acceptance Scenarios**:

1. **Given** a WP in `in_review` and a structured review result carrying a reference, **When**
   any status door moves it to `in_progress`, **Then** the event records that reference as
   `review_ref` and the payload validates against the vendored contract.
2. **Given** the same fixture and a caller who supplied `--review-ref` explicitly, **When** the
   move runs, **Then** the caller's pointer is recorded unchanged and the existing
   review_ref/review_result consistency rule still applies (positive control on the same
   fixture).

---

### User Story 2 - No write door appends a pointerless in_review rewind (Priority: P2)

The same rewind can be requested without any review evidence at all. That request must be
refused before the append, with the log byte-identical afterwards, and the same request again
with a structured review result must land — so the refusal is a real gate, not a blind probe.

**Why this priority**: Without it the reported bug is fixed on one door while the other doors
keep poisoning the append-only ledger. #6514 and #6955 established this parity requirement.

**Independent Test**: On a fixture mission with WP01 in `in_review`, send the pointerless forced
rewind through `agent status emit` and assert exit non-zero, the `review_ref` message, and
`status.events.jsonl`/`status.json` SHA-256 unchanged; then send it with `--review-result-json`
and assert exactly one row appended and `status validate` exit 0.

**Acceptance Scenarios**:

1. **Given** a WP in `in_review`, **When** `agent status emit --to in_progress --force --reason
   "<why>"` runs with no `--review-ref` and no review result, **Then** it exits non-zero naming
   `review_ref`, and the log and materialized status are byte-identical.
2. **Given** the same fixture, **When** the same command adds a structured review result with a
   reference, **Then** it appends exactly one row and `status validate` passes.
3. **Given** a pointerless `in_review -> in_progress` row already in a log, **When** `status
   validate` runs, **Then** it reports that row and the documented append-only position tells
   the operator what may be done about it.

---

### User Story 3 - The rule has one owner, matches the contract, and cannot rot (Priority: P3)

A maintainer reads one predicate and sees an edge set that is a subset of the vendored
contract's gated family, with the writer, the auditor and the emitter all reading it — and the
pin that guarded the deferral now guards the closure instead of blocking it.

**Why this priority**: It is what keeps this class of divergence from reappearing on the next
edge; it is also what stops the #6955 deferral from flipping silently in either direction.

**Independent Test**: A ratchet test enumerates the local set, asserts every member is a real
wire requirement of the pinned dependency (pointerless forced payload invalid, `force-override`
payload valid, same fixture), asserts the set is a subset of the contract's gated family, and
asserts the reported edge is a member.

**Acceptance Scenarios**:

1. **Given** the local definition, **When** a test enumerates it, **Then** `(in_review,
   in_progress)` is a member, every member is proven to be a real contract requirement, and the
   set contains no edge the contract does not gate.
2. **Given** a forced pointerless request on a non-member edge, **When** the writer is probed,
   **Then** it is still admitted exactly as before (no widening beyond this edge).

---

### Edge Cases

- **Whitespace-only structured reference**: not a pointer. The derivation copies only a
  non-blank string, so a blank `review_result.reference` leaves `review_ref` absent; the
  `in_review` guard already refuses a blank reference, and the new gate refuses the pointerless
  event.
- **Caller-supplied pointer wins**: when `review_ref` is already set the derivation is a no-op,
  so an explicit `--review-ref` is recorded unchanged and a mismatch with
  `review_result.reference` is still refused by the existing consistency rule.
- **`migration:` actors** restating history: exempt from the write-path refusal (the #5446
  precedent); the auditor still reports such a row, and the docs say so.
- **A legacy pointerless row** already in a committed mission log: never rewritten; the auditor
  reports it and the append-only correction position applies.
- **The `approved -> in_progress` edge** is not this mission's: it stays exactly as it is on
  this base (gated by #6955/PR #7102, not in the local set here), and no test here asserts
  either state for it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | The emit path derives the wire pointer | As an operator, I want a structured review result's reference recorded as the event's `review_ref` when I supplied no pointer, so that the recorded row is one hosted sync accepts. | High | Open | [build] | no |
| FR-002 | The reported edge is gated | As a maintainer, I want `in_review -> in_progress` in `REVIEW_REF_REQUIRED_EDGES` so the writer refuses a pointerless row before the append. | High | Open | [build] | no |
| FR-003 | No door appends a pointerless in_review rewind | As an operator, I want every write door to refuse a pointerless `in_review -> in_progress` before appending, with the ledger byte-identical, and the same request carrying evidence to land. | High | Open | [build] | no |
| FR-004 | The auditor reports a stored pointerless row | As a maintainer, I want `status validate` to report an `in_review -> in_progress` row without a pointer, so an existing poisoned ledger is visible. | Medium | Open | [build] | no |
| FR-005 | The #6955 pin flips deliberately and keeps its intent | As a maintainer, I want the deferral pin to move with an explicit reason and the ratchet to stay merge-order independent, so the flip is never silent. | High | Open | [ratchet] | no |
| FR-006 | Every other edge is untouched | As an operator, I want every other forced edge — including `approved -> in_progress` and `in_review -> planned` — to behave exactly as it does on this base. | High | Open | [ratchet] | no |
| FR-007 | A caller's pointer is never overridden | As a maintainer, I want the derivation to fill only an absent pointer, so an explicit `--review-ref` and the existing consistency refusal keep their behaviour. | High | Open | [ratchet] | no |
| FR-008 | The reference states the family and the recovery position | As an operator, I want the status-model reference to name the three gated edges, the pointer each writer supplies, and the append-only position for pre-fix rows. | Medium | Open | [build] | no |
| FR-009 | The vendored contract is not modified | As a maintainer, I want the fix to conform the payload rather than change or re-pin `spec-kitty-events`, so no cross-repository contract decision is taken here. | High | Open | [ratchet] | yes — guarded by the same-fixture assertion that the pinned package is read, not patched |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| NFR-001 | Zero-byte failure footprint | A refused pointerless rewind leaves `status.events.jsonl` and `status.json` byte-identical (SHA-256 unchanged), asserted on the same fixture as the successful append. | Reliability | High | Open |
| NFR-002 | No new I/O on the decision path | The derivation reads only fields already on `TransitionRequest`; `prepare_transition` performs no new file read, subprocess or network call (asserted by a no-I/O probe on the pipeline). | Performance | Medium | Open |
| NFR-003 | No new refusal outside the gated family | Across the full lane-pair parity matrix the writer's verdicts change on exactly the `in_review -> in_progress` rows this change is meant to move — enumerated by the golden truth table. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | The wire contract is consumed, never changed | The mission does not edit, vendor, patch or re-pin `spec-kitty-events`; the emitted payload conforms to the pinned contract. | Technical | High | Open |
| C-002 | No gate is weakened | The derivation only fills an *absent* pointer from evidence the same request already carries; it does not admit a request that cites no review evidence, and an explicit blank pointer is still refused. | Business | High | Open |
| C-003 | Append-only history | No code or migration rewrites, corrects or back-fills an already-written event row; recovery stays an operator-append decision documented in the reference. | Technical | High | Open |
| C-004 | Single canonical definition | `status/wp_state.py::REVIEW_REF_REQUIRED_EDGES` stays the only definition of "this edge requires a `review_ref`"; the pointer derivation lives only in `transition_pipeline.prepare_transition`, the tree's single validation/event-build authority. | Technical | High | Open |
| C-005 | Release scope untouched | No version bump and no `CHANGELOG.md` `[Unreleased]` edit; the change ships as a per-PR fragment under `docs/changelog/unreleased/`. | Business | Medium | Open |
| C-006 | One edge, not a family rewrite | The change does not take over the `approved` edge (#6955/PR #7102) and does not extend to `* -> planned`, `done`/`canceled` exits or any forward edge. | Technical | High | Open |

### Key Entities *(include if the mission involves data)*

- **`REVIEW_REF_REQUIRED_EDGES`**: the single local definition of the edges whose persisted
  event must carry a `review_ref`; read by the writer (`WPState.check_transition`), the auditor
  (`status.validate.validate_event_schema`) and the emitter (`build_transition_plan`'s sentinel
  fill).
- **`prepare_transition`**: the tree's only validation and event-build authority; every status
  door (flat, batch, transactional, coordination) reaches it. Its derived pointer is the one
  the guard sees and the one the event records.
- **`ReviewResult.reference`**: the structured evidence a review exit already carries; the
  derivation source when no explicit pointer was supplied.
- **`StatusEvent.review_ref`**: the pointer recorded on the append-only row; a non-blank string
  satisfies the requirement, `null`/blank does not.
- **Gated rewind family**: the contract's `{for_review, in_review, approved} -> in_progress`;
  this mission closes `in_review` locally, on top of #6514's `for_review`, with `approved`
  owned by #6955/PR #7102.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's exact probe flips — `requires_review_ref("in_review", "in_progress")` is `True`, the writer refuses the pointerless forced rewind, and a row emitted from a structured review result validates against the pinned `spec_kitty_events` contract (pre-fix: `False`, admitted, invalid). — [build] · no-op passable: no
- **SC-002**: A pointerless forced `in_review -> in_progress` through `agent status emit` exits non-zero with the log SHA-256 unchanged; the same request with a structured review result appends one row and `status validate` exits 0 — 2/2 observations on one fixture. — [build] · no-op passable: no
- **SC-003**: Every member of the local edge set is proven to be a real requirement of the pinned dependency (pointerless forced payload invalid, pointer-carrying payload valid) and the set is a subset of the contract's gated family; `(in_review, in_progress)` is a member. — [ratchet] · no-op passable: no
- **SC-004**: The golden parity truth table moves only on the `in_review -> in_progress` / `in_review -> doing` rows: the four `[force_full]` and `[review_result]` verdicts flip `True -> False`, and that edge's other pointerless rows keep their `False` verdict while reporting the `review_ref` refusal instead of the `review_result` guard's message. No other edge moves. — [ratchet] · no-op passable: no
