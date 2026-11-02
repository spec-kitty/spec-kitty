# Mission Specification: Wire-valid approved reopen

**Mission Branch**: `kitty/mission-wire-valid-approved-reopen-01M6EJW0`
**Created**: 2026-11-02
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6955 — A forced approved reopen without feedback records a wire-invalid transition event. `move-task --to in_progress` on an approved work package without `--review-feedback-file` records `approved -> in_progress` with `force: true` and `review_ref: null`, a payload the vendored `spec_kitty_events.status.validate_transition` rejects, so hosted sync silently rejects it (#3307 class). Ground it, fix it red-first, keep the force-provenance policy (`wp-runtime-state-eviction-01KXWN13#FR-015`) and the vendored contract untouched, changelog fragment, draft PR, never merge."

## Problem Statement

An approved work package reopened for rework without review-feedback evidence records a
status event the shared wire contract refuses.

Reproduced on `main` @ `9aed3a8012` through the production planner
(`build_transition_plan`, the function `move-task` calls) and through the writer
(`wp_state_for("approved").check_transition`):

```
plan(approved -> in_progress, no feedback) =
  TransitionPlan(canonical_lane='in_progress', transition_targets=['in_progress'],
                 emit_force=True, emit_reason='backward rewind: approved -> in_progress',
                 emit_review_ref=None)
wire validate_transition(that payload) -> valid=False
```

The vendored contract (`spec_kitty_events.status`, "Review-Ref-Gated Rewind Family") gates
three rewinds to `in_progress` on a non-empty `review_ref` — `for_review`, `in_review` and
`approved` — and states the requirement holds "whether the event is forced or not". The
local rule that the writer and the auditor both read,
`status/wp_state.py::REVIEW_REF_REQUIRED_EDGES`, lists only `for_review -> in_progress`.
That divergence is the defect: the emitted row is locally accepted (and locally audited as
clean) while the shared contract the SaaS ingestion endpoint enforces rejects it.

The same probe shows the sibling divergence on `in_review -> in_progress`: the writer
accepts a pointerless forced payload (`(True, None)`) that the wire contract rejects. Only
`for_review -> in_progress` is already gated.

### The decision the issue asks for, and the arm taken here

The issue poses a fork: **(a)** require feedback evidence for every approved reopen and
refuse the bare arm, or **(b)** keep the forced reopen and re-pin the wire contract to
admit it. Neither is needed:

- **(b) is out of reach and out of scope.** The contract lives in the released
  `spec-kitty-events` dependency, which core consumes by pin; re-pinning or amending it is a
  cross-repository contract change (a maintainer/upstream decision), and this mission
  touches neither the pin nor the vendored package (`C-001`).
- **(a) is a change to the force-provenance policy** (`wp-runtime-state-eviction-01KXWN13#FR-015`) that the #6845 landing pass deliberately preserved
  ("a missing reference retains its documented forced behavior and is never described as
  force-free"). Removing that arm needs a maintainer ruling this issue does not carry.

The contract does not actually require either: a forced rewind is valid as soon as it cites
a `review_ref`, and the project already owns a sanctioned, non-resolvable reference for
exactly this situation — `force-override`, a member of
`review.cycle.REVIEW_FEEDBACK_SENTINELS`. `move-task` already stamps it on the sibling
forced `for_review -> in_progress` rewind (#6514), and
`status/work_package_lifecycle.py::start_implementation_status` already stamps it on this
very `approved -> in_progress` forced withdraw (`agent action implement`). So the conforming
shape exists and one door already emits it; `move-task` is the outlier. This mission makes
`move-task` match: the forced arm is **kept** (force policy untouched) and the emitted row **cites
the sentinel** instead of `null`, so the payload conforms without re-pinning anything and
without inventing a feedback pointer that does not exist.

The mission extends that one owning definition (`C-004`) with the reported edge and keeps
the emitter's existing sentinel fill as the conforming answer on every door. The contract's
third gated edge, `in_review -> in_progress`, is **not** taken here: its evidence is a
structured `review_result` that the status emit path never turns into a `review_ref`, so
gating it without that second fix would refuse legitimate writes (proven in the same probe
under `R1`). It is filed as follow-up #7080, remains accepted locally until then, and that
carve-out is pinned by a test so it cannot silently flip.

Scope boundary: this mission fixes the local predicate and the `move-task` emission. It does
not re-pin `spec-kitty-events`, does not add a new sentinel, does not change the force-provenance
evidence rule, and does not rewrite historical event rows.

### Pre-existing regression found on the same edge during grounding

`main` currently refuses `--review-feedback-file` on `approved -> in_progress` itself:
`_feedback_edge_recordable` (#6699, committed 2026-11-02T09:21Z) admits only review-rejection
edges and the approval lanes, so the approved reopen is treated as an edge that "writes no
review cycle" and is refused before the file is ever read. #6699 landed **before** the #6845
landing fix (`d3e60abf5e`, 13:35Z), but that landing pass re-ran only the fast gate — the
contract test it amended is `integration`/`git_repo`-marked — so it shipped the evidence arm
already broken and nothing noticed:
`tests/integration/test_owned_reopen_feedback.py` fails on `main` today for its `provided`
and `empty` kinds.

That arm is not collateral here: FR-004 cannot be honest while it is broken, and the
mission's own claim ("a supplied feedback file still wins") becomes false. The fix belongs
in the same diff and is the same class of correction: the approved reopen **does** record
the supplied file — as the event's `review_ref` — so it is a recordable edge (#6699's own
premise), and `_feedback_edge_recordable` must say so. This mission therefore restores the
arm (`FR-004`) and keeps both halves proven red-first: `provided`/`empty` red for the
restore, `absent` red for the sentinel.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A forced reopen records an event hosted sync accepts (Priority: P1)

An operator discovers a defect in an approved work package and reopens it for rework. They
have no review-feedback file to cite; the reopen is an operator decision, forced. The
recorded status event must be one the shared contract accepts, so the row is not silently
dropped at sync.

**Why this priority**: This is the reported defect and the reason the issue is open.

**Independent Test**: Drive `move-task --to in_progress` on an approved WP with no
`--review-feedback-file` through the real CLI (owned-checkout integration fixture), read the
last `status.events.jsonl` row, and assert `force is True` and
`review_ref == "force-override"`; rebuild that exact row as a
`spec_kitty_events.status.StatusTransitionPayload` and assert `validate_transition(...).valid`
is `True`. On the pre-fix tree the same assertion fails (`review_ref is None`,
`valid is False`).

**Acceptance Scenarios**:

1. **Given** an approved work package and no feedback file, **When** an operator runs
   `move-task WP01 --to in_progress`, **Then** the event records `force: true` with
   `review_ref: "force-override"` and the payload validates against the vendored contract.
2. **Given** the same fixture with a usable `--review-feedback-file`, **When** the operator
   reopens, **Then** the event is still force-free and cites the supplied file path — the
   #6845 evidence arm is unchanged (positive control on the same fixture).

---

### User Story 2 - No write door appends a pointerless gated rewind (Priority: P2)

The same rewind can be requested through `agent status emit` or `orchestrator-api wp
transition`. A pointerless request must be refused before the append, with the log
byte-identical afterwards, and the same request carrying `--review-ref` must land — so the
refusal is a real gate, not a blind probe.

**Why this priority**: Without it the reported bug is fixed on one door while the other
doors keep poisoning the append-only ledger. #6514 established this parity requirement.

**Independent Test**: Through the CLI on a fixture mission, send the pointerless forced
rewind on the gated family through `agent status emit` and assert exit non-zero, the
`review_ref` message, and `status.events.jsonl`/`status.json` SHA-256 unchanged; then send
the same request with `--review-ref force-override` and assert one row appended and
`status validate` exit 0.

**Acceptance Scenarios**:

1. **Given** a WP in `approved`, **When** `agent status emit --to in_progress --force
   --reason "<why>"` runs with no `--review-ref`, **Then** it exits non-zero naming
   `review_ref`, and the log and materialized status are byte-identical. (The deferred
   `in_review` edge still admits the same request; #7080.)
2. **Given** the same fixture, **When** the same command adds `--review-ref <pointer>`,
   **Then** it appends exactly one row and `status validate` passes.
3. **Given** a pointerless `approved -> in_progress` row already in a log, **When**
   `status validate` runs, **Then** it reports that row (the new auditor verdict) and the
   documented append-only position tells the operator what may be done about it.

---

### User Story 3 - The rule has one owner and matches the contract (Priority: P3)

A maintainer reads one predicate and sees the same edge set the vendored contract declares,
with the writer, the auditor and the emitter all reading it — so the next contract revision
cannot silently re-split them.

**Why this priority**: It is what keeps this class of divergence from reappearing on the
next edge; without it the fix is two literals in three places.

**Independent Test**: A ratchet test enumerates the local set and the vendored contract's
gated family and asserts they are equal, and for each member asserts a pointerless forced
payload is *wire-invalid* while a `force-override`-carrying payload is *valid*.

**Acceptance Scenarios**:

1. **Given** the local definition, **When** a test enumerates it, **Then** it equals
   `{(for_review, in_progress), (approved, in_progress)}`, each member is proven to be a
   real wire requirement on the pinned dependency, and the deferred `in_review` edge is
   proven to still be a contract requirement that the local writer does not yet gate.

---

### Edge Cases

- **Whitespace-only `review_ref`**: treated as absent (`has_review_ref` already strips), so
  a `--review-ref "   "` on a gated family edge is refused, not recorded blank.
- **`migration:` actors** restating history: exempt from the force-insurmountable rule (the
  #5446 precedent); the auditor still reports such a row, and the docs say so.
- **A legacy pointerless row** already in a committed mission log: never rewritten; the
  auditor reports it and the append-only correction position applies.
- **`approved -> planned`** (a review-rejection edge) is *not* in the gated rewind family:
  its `review_ref` is optional even when forced, and it keeps its own guard and message.
- **Explicit `--force` plus a real `--review-feedback-file`**: the file pointer wins over the
  sentinel (the supplied, resolvable evidence is recorded).
- **A forced reopen of a WP whose mission log is written by another process**: out of scope;
  the refusal happens in validation before the lock-protected append.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | The forced approved reopen cites the sentinel | As an operator, I want the forced `approved -> in_progress` row to cite `force-override` instead of `null`, so that the event hosted sync ingests is wire-valid. | High | Open | [build] | no |
| FR-002 | One predicate covers the gated edges this mission claims | As a maintainer, I want `REVIEW_REF_REQUIRED_EDGES` to hold exactly the gated edges this mission closes (`for_review`, `approved`) with the deferred `in_review` edge named and pinned as follow-up #7080, so that the writer, the auditor and the emitter cannot disagree with each other or drift silently from the contract. | High | Open | [build] | no |
| FR-003 | No door appends a pointerless gated rewind | As an operator, I want every write door (`move-task`, `agent status emit`, `orchestrator-api wp transition`) to refuse a pointerless gated rewind before appending, so that no door can poison the append-only ledger. | High | Open | [build] | no |
| FR-004 | The evidence arm is restored and unchanged | As a maintainer, I want a reopen with usable feedback to be force-free and cite that file (the behaviour #6845 decided and the #6699 merge order broke), and empty/missing feedback to stay refused, so that the FR-015 evidence arm is real again and not regressed. | High | Open | [build] | no |
| FR-005 | The other door's sentinel is unchanged | As an operator, I want `agent action implement`'s forced pointerless withdraw to keep landing with its sentinel. | Medium | Open | [ratchet] | no |
| FR-006 | Every other forced edge is untouched | As an operator, I want `done`/`canceled` exits, `in_progress -> planned`, `for_review -> planned` and every other forced edge to behave exactly as today. | High | Open | [ratchet] | no |
| FR-007 | The reference states the family and the recovery position | As an operator, I want the status-model reference to name the gated family, the pointer each writer supplies, and the append-only position for pre-fix rows. | Medium | Open | [build] | no |
| FR-008 | The auditor keeps its migration exemption | As a maintainer, I want a `migration:` actor still admitted by the writer while the auditor reports its rows, so that reconstruction is not blocked. | Medium | Open | [ratchet] | no |
| FR-009 | The vendored contract is not modified | As a maintainer, I want the fix to conform the payload rather than change or re-pin `spec-kitty-events`, so that no cross-repository contract decision is taken here. | High | Open | [ratchet] | yes — guarded by a same-fixture assertion that the pinned package's gated family is read, not patched |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero-byte failure footprint | A refused gated rewind leaves `status.events.jsonl` and `status.json` byte-identical (SHA-256 unchanged), asserted on the same fixture as the successful append. | Reliability | High | Open |
| NFR-002 | No new I/O on the decision path | The widened predicate adds no file read, subprocess or network call: `build_transition_plan` stays pure and the guard reads only facts already in `MoveTaskRequest` (asserted by the existing purity/no-I/O test style plus a call-count probe). | Performance | Medium | Open |
| NFR-003 | No new refusal outside the family | Across the full lane-pair matrix, the set of (from, to) pairs the writer refuses is unchanged except the two added family edges — enumerated by a matrix test. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | The wire contract is consumed, never changed | The mission does not edit, vendor, patch or re-pin `spec-kitty-events`; the emitted payload conforms to the pinned contract (issue option (b) is declined as a cross-repo decision). | Technical | High | Open |
| C-002 | Force policy unchanged | The force-provenance evidence rule (`wp-runtime-state-eviction-01KXWN13#FR-015`) and #5446's bare-force-`--note` rule are preserved: no widening of force reach, no new narrowing of the documented forced arm beyond citing a reference the contract already requires. | Business | High | Open |
| C-003 | Append-only history | No code or migration rewrites, corrects or back-fills an already-written event row; recovery stays an operator-append decision documented in the reference. | Technical | High | Open |
| C-004 | Single canonical definition | `status/wp_state.py::REVIEW_REF_REQUIRED_EDGES` stays the only definition of "this edge requires a `review_ref`"; no second literal set appears in the emitter, the doors or the auditor. | Technical | High | Open |
| C-005 | Release scope untouched | No version bump and no `CHANGELOG.md` `[Unreleased]` edit; the change ships as a per-PR fragment under `docs/changelog/unreleased/`. | Business | Medium | Open |
| C-006 | One edge family, not general force | The change does not extend to `* -> planned` (review-rejection family), `done`/`canceled` exits or any forward edge. | Technical | High | Open |

### Key Entities *(include if the mission involves data)*

- **`REVIEW_REF_REQUIRED_EDGES`**: the single local definition of the edges whose persisted
  event must carry a `review_ref`; read by the writer (`WPState.check_transition`), the
  auditor (`status.validate.validate_event_schema`) and the emitter
  (`build_transition_plan`'s sentinel fill).
- **`StatusEvent.review_ref`**: the pointer recorded on the append-only row; a non-blank
  string satisfies the requirement, `null`/blank does not.
- **`force-override`**: the sanctioned, non-resolvable operational sentinel
  (`review.cycle.REVIEW_FEEDBACK_SENTINELS`) meaning "an operator drove this rewind"; already
  emitted on `for_review -> in_progress` and by `start_implementation_status`.
- **Gated rewind family**: the contract's `{for_review, in_review, approved} -> in_progress`;
  this mission closes `for_review`+`approved` locally, with `in_review` deferred to #7080, as declared by
  the vendored contract's "Review-Ref-Gated Rewind Family" section.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's exact repro — `move-task --to in_progress` on an approved WP with no feedback — records `force: true` + `review_ref: "force-override"`, and that payload validates against the pinned `spec_kitty_events` contract (pre-fix: `null` and invalid). — [build] · no-op passable: no
- **SC-002**: A pointerless forced gated rewind through `agent status emit` exits non-zero with the log SHA-256 unchanged; the same request with `--review-ref force-override` appends one row and `status validate` exits 0 — 2/2 observations on one fixture. — [build] · no-op passable: no
- **SC-003**: The local edge set is exactly the two gated edges this mission claims, a ratchet proves each is a real requirement of the pinned dependency, and the deferred contract edge (`in_review -> in_progress`) is both proven still gated on the wire and pinned as still admitted locally. — [ratchet] · no-op passable: no
- **SC-004**: The #6845 evidence arm is working and unchanged: usable feedback → `force: false` + file pointer; empty/missing feedback → refusal, log unchanged (2/2 on the same fixture; both are red on `main` today for the `provided`/`empty` kinds). — [build] · no-op passable: no
- **SC-005**: Across the lane-pair matrix, the writer refuses exactly the family edges more than before (2 added pairs, 0 others). — [ratchet] · no-op passable: no
