# Mission Specification: Reject invalid forced status rewinds before append

**Mission Branch**: `reject-invalid-forced-status-rewind-01M68J8B`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6514 — Reject invalid forced status rewinds before append. A forced status rewind that is invalid is appended to the log before validation, so the ledger records a transition that should have been refused. Reproduce, then validate before the append (no partial state on refusal), and pin it. Cite pre-existing reds (#6798/#6801/#6816/#5927). Never merge."

## Problem Statement

`spec-kitty agent status emit` and `spec-kitty orchestrator-api wp transition` accept a
forced `for_review → in_progress` transition that carries a `--reason` but no
`--review-ref`. The write path appends the row and reports success. `spec-kitty agent
status validate` then refuses the same row, because every `for_review → in_progress`
event requires a `review_ref`. The log is append-only, so the malformed row is
permanent: a command that reported success left the mission's canonical ledger in a
state its own auditor calls invalid.

Measured on `main` @ `35318ef51c`, through the real CLI:

```
# planned -> claimed -> in_progress -> for_review via agent status emit
$ spec-kitty agent status emit WP01 --to in_progress --actor codex \
    --force --reason "source boundary changed"
exit 0, log grows 4 -> 5 rows
row: {"from_lane":"for_review","to_lane":"in_progress","force":true,
      "reason":"source boundary changed","review_ref":null}

$ spec-kitty agent status validate --mission 017-test-feature
exit 1
"Event 01M68J63NCYKK6X90EG8HYNE6K: for_review->in_progress without review_ref"
```

The two authorities disagree because the invariant lives only in the auditor:
`status/validate.py::validate_event_schema` demands the pointer, while
`status/wp_state.py` has no such rule — `for_review` has no backward edge, so
`for_review → in_progress` is *force-only*, and the force gate checks nothing but
actor + reason. The writer and the auditor are therefore allowed to disagree by
construction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The ledger never records a rewind its own auditor refuses (Priority: P1)

An operator rewinds a work package out of review because the source boundary moved.
They force the transition with a reason, but they do not have a review-feedback
pointer to cite. Today the command succeeds and poisons the log. The operator needs
the command to refuse *before* writing, leaving the log and the materialized status
exactly as they were, so the failure is fixable and the ledger stays valid.

**Why this priority**: This is the defect. Everything else in this mission supports it.

**Independent Test**: Drive the reproduction above through `agent status emit` on a
fixture mission and assert: exit non-zero, `status.events.jsonl` byte-identical,
`status.json` byte-identical, and `agent status validate` still exits 0. Then re-run
the same command with `--review-ref` and assert it appends and validates — the positive
control on the same fixture proves the probe can see a successful append.

**Acceptance Scenarios**:

1. **Given** a work package in `for_review`, **When** an operator runs
   `agent status emit WP01 --to in_progress --actor codex --force --reason "<why>"`
   with no `--review-ref`, **Then** the command exits non-zero, names the missing
   pointer and the flag that supplies it, and appends nothing.
2. **Given** the same work package after that refusal, **When** the operator runs
   `agent status validate --mission <slug>`, **Then** validation still passes, because
   no invalid row was written.
3. **Given** the same work package, **When** the operator re-runs the same forced
   rewind **with** `--review-ref <pointer>`, **Then** the transition is appended and
   `status validate` passes — the legal override is preserved.

---

### User Story 2 - Every write door gets the same answer (Priority: P2)

The same forced rewind can be requested through `orchestrator-api wp transition`. A fix
pasted into one CLI command would leave the other door open and the two surfaces free
to drift again.

**Why this priority**: It is what makes the fix a single authority instead of a patch.

**Independent Test**: Send the identical invalid request through
`orchestrator-api wp transition` and assert the same refusal with no append, while the
pointer-carrying request succeeds on both doors.

**Acceptance Scenarios**:

1. **Given** a work package in `for_review`, **When** any supported write door requests
   a forced `for_review → in_progress` with no `review_ref`, **Then** every door refuses
   with the same rule and the same no-partial-state guarantee.

---

### User Story 3 - An operator can find out what to do about rows already written (Priority: P3)

Missions that already hold such a row (the reporting consumer had three) need an
honest answer. The documented position must say that the bytes are never rewritten,
what the auditor reports, and which append-only route an operator may take.

**Why this priority**: Documentation cannot prevent the defect, but a missing answer
is what turns a permanent row into a permanent guess.

**Independent Test**: Read the updated status-model documentation and check it states
the refusal, the no-rewrite rule, and the supported recovery shape; grep it for the
new guard so a future edit cannot silently drop it.

**Acceptance Scenarios**:

1. **Given** the published status-model reference, **When** a reader looks up
   `for_review → in_progress`, **Then** they find the `review_ref` requirement stated
   as force-insurmountable, and the append-only recovery position for pre-fix rows.

---

### Edge Cases

- **Whitespace-only `--review-ref`** (for example `--review-ref "   "`): treated as
  absent, exactly as `move-task`'s existing `review_ref.strip()` checks treat it.
- **A forced rewind that carries a pointer**: must still append. `move-task` already
  does this on this edge with the `force-override` sentinel; that path must stay green.
- **Other force-only edges** (`done → <lane>`, `canceled → <lane>`, `planned →
  in_progress`, `for_review → planned`): unchanged. The new requirement is scoped to
  the one edge the auditor refuses, not to force in general.
- **`in_review → in_progress`** (a legal, structurally-allowed edge): unchanged. It is
  a different edge with its own guard and its own #5446 force-note rule.
- **A migration or reconstruction actor** restating history: the FSM rule is about the
  event's shape, not the actor, so it applies to every writer. No exemption is added.
- **Refusal while the log is mid-write from another process**: out of scope — the
  refusal happens in the pure validation step, before any lock-protected append.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Refuse the pointerless forced rewind | As an operator, I want a forced `for_review → in_progress` with no `review_ref` refused before it is written, so that my ledger never records an event its own auditor rejects. | High | Open | [build] | no |
| FR-002 | Refusal writes nothing | As an operator, I want a refused rewind to leave the event log and the materialized status byte-identical, so that a failure never leaves partial state to clean up. | High | Open | [build] | no |
| FR-003 | Refusal names the remedy | As an operator, I want the refusal to name the missing `review_ref` and the flag that supplies it, so that I can fix the command instead of guessing. | High | Open | [build] | no |
| FR-004 | The legal pointer-carrying rewind still lands | As an operator, I want the same forced rewind to succeed when I do supply a pointer, so that force still works for legal overrides. | High | Open | [ratchet] | no |
| FR-005 | One rule for every write door | As a maintainer, I want the rule to live in the status validation authority so `agent status emit` and `orchestrator-api wp transition` cannot disagree, so that the writer/auditor mismatch cannot reappear on the other door. | High | Open | [build] | no |
| FR-006 | The auditor and the writer share one source | As a maintainer, I want the "this edge requires `review_ref`" fact to have one owning definition that both the write path and `validate` read, so that a future edit cannot re-split them. | Medium | Open | [build] | no |
| FR-007 | Other force overrides are untouched | As an operator, I want every other forced edge to behave exactly as it does today, so that closing this hole does not narrow force in general. | High | Open | [ratchet] | no |
| FR-008 | `move-task`'s forced rewind is untouched | As an operator, I want `move-task`'s existing forced `for_review → in_progress` rewind (which supplies the `force-override` sentinel) to keep working, so that the fix does not break the surface that already conforms. | High | Open | [ratchet] | no |
| FR-009 | Both doors refuse identically | As an operator, I want the same invalid request refused the same way through either supported write door, so that I do not have to learn per-door behaviour. | Medium | Open | [build] | no |
| FR-010 | Documented append-only recovery position | As an operator holding an already-written invalid row, I want the status reference to state the no-rewrite rule and the supported append-only route, so that I know what is and is not safe. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero-byte failure footprint | A refused rewind leaves `status.events.jsonl` and `status.json` byte-identical: the SHA-256 of each file is unchanged across the refused invocation, asserted on the same fixture as the successful append. | Reliability | High | Open |
| NFR-002 | No added round trips on the legal path | The pointer-carrying rewind performs no additional file read or subprocess beyond what the write path already does; the rule is evaluated from the request already in hand. | Performance | Medium | Open |
| NFR-003 | Refusal is observable in `--json` | In `--json` mode the refusal exits 1 and emits a parseable object whose `error` contains the `review_ref` requirement; no lane or event id is claimed. | Usability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | Single canonical authority | The `review_ref`-required edge predicate has exactly one owning definition, consumed by both the write path (`status/wp_state.py`) and the auditor (`status/validate.py`). A second copy fails the charter's canonical-source principle. | Technical | High | Open |
| C-002 | Append-only history | No code or migration rewrites the bytes of an already-written event. Recovery is append-only and auditable. | Technical | High | Open |
| C-003 | No force-policy widening | The change narrows one illegal write; it does not relax any guard, does not grant force any new reach, and does not touch `in_review`/`approved` force-note policy (#5446). | Business | High | Open |
| C-004 | Release scope untouched | Issue #6514 stays at provisional `priority:P2` with no milestone change; this mission does not promote it. | Business | Medium | Open |

### Key Entities *(include if the mission involves data)*

- **`for_review → in_progress` edge**: the one lane transition this mission governs. It
  is not a structural edge in the FSM, so force is its only route, and `validate`'s
  schema rule is its only existing constraint.
- **`review_ref`**: the review-feedback pointer a rewind must cite. `move-task` supplies
  the `force-override` sentinel on this edge; the generic transition doors pass through
  whatever the caller provides, including nothing.
- **`StatusEvent`**: the immutable append-only row. Its `review_ref` field is what the
  rule and the auditor both read.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The exact reproduction from #6514, run through `agent status emit`, exits non-zero with the event log unchanged in row count and SHA-256. — [build] · no-op passable: no
- **SC-002**: `spec-kitty agent status validate --mission <slug>` exits 0 after the refused command, on the same fixture the pre-fix log failed on. — [build] · no-op passable: no
- **SC-003**: The same forced rewind with a non-empty `--review-ref` appends one row and validates clean on that fixture. — [ratchet] · no-op passable: no · paired positive control for SC-001/SC-002 on the same fixture
- **SC-004**: The two supported write doors return the same refusal for the same invalid request: 2 of 2 doors, 0 appended rows. — [build] · no-op passable: no
- **SC-005**: `move-task`'s forced `for_review → in_progress` rewind still exits 0 and still records the rewind, so the conforming surface is provably untouched. — [ratchet] · no-op passable: no
- **SC-006**: A reader of the status-model reference finds the force-insurmountable `review_ref` requirement and the no-rewrite recovery position in the `for_review → in_progress` entry. — [build] · no-op passable: no
