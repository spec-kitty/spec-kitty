# Mission Specification: Implement resumes after in_review to in_progress rejection

**Mission Branch**: `ccr-806fafb9-5qycab`
**Created**: 2026-09-29
**Status**: Draft
**Input**: GitHub issue #5377 — "agent action implement refuses the implementer's resume after an in_review → in_progress rejection (WorkPackageClaimConflict)". P0, 4.0.0 release scope; parent epic: see #3044.

## Intent Summary

A reviewer may reject a work package with the unforced `in_review → in_progress`
route (a rework verdict carrying a `review_ref`). The implementer must then be able
to resume that work package with `spec-kitty agent action implement WP## --agent
<implementer>` without `--force`. Today the resume is refused with
`WorkPackageClaimConflict` ("already claimed for implementation by '<reviewer>'"),
because the claim check compares the requester against the actor of the latest
status event — which, after the rejection, is the reviewer. The ordinary
review loop dead-ends. The `→ planned` rejection route already works.

PR #5316 removed the same class of refusal from `move-task` by resolving "who is
the WP's latest implementer" through the pure `status.review_roles` projection
(`latest_implementer_actor`), which skips reviewer rework verdicts. The claim
check in the shared implementation-start authority does not use it yet; this
mission closes that residual (PR #5316 named it in its Deferred section).

Decision (DM `resume_scope`): only the implementer of record may resume, and the fix
lands in the shared implementation-start authority so every caller of it (the
`agent action implement` command, the `implement` compatibility command, the
orchestrator API start-implementation command) inherits the same ownership rule.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Implementer resumes rework after an in_progress rejection (Priority: P1)

An implementer agent submitted WP01 for review. A reviewer agent (a different tool)
claimed it (`for_review → in_review`) and rejected it back to `in_progress` with
review feedback. The implementer runs `agent action implement WP01 --agent
<implementer>` to pick up the rework.

**Why this priority**: without it the ordinary reject → rework → resubmit loop
cannot complete without `--force`, which the review-integrity epic forbids as a
routine path. P0 release blocker.

**Independent Test**: drive the real CLI through implement → for_review →
in_review → reject to in_progress, then run implement as the implementer: it must
exit 0, append no forced event, and enter fix mode from the rejection's review cycle.

**Acceptance Scenarios**:

1. **Given** WP01 was rejected `in_review → in_progress` by the reviewer with a review
   feedback file, **When** the implementer of record runs `agent action implement
   WP01 --agent <implementer>`, **Then** the command exits 0, appends no lane event (the resume is an idempotent no-op on the lane), and nothing it writes is forced.
2. **Given** the same state, **When** the implementer resumes, **Then** the resume
   is recognised as rework (fix mode against the latest review cycle), exactly as the
   `→ planned` rejection route does today.

---

### User Story 2 - Unrelated agents stay refused (Priority: P1)

**Why this priority**: the allowance must not become an ownership bypass.

**Independent Test**: same fixture; an agent on a third tool runs implement and is refused.

**Acceptance Scenarios**:

1. **Given** WP01 was rejected `in_review → in_progress` by the reviewer, **When** an
   agent that is neither the implementer of record nor the slot occupant runs
   implement without `--force`, **Then** it is refused with `WorkPackageClaimConflict`
   and no status event is written.
2. **Given** the latest-implementer read fails, **When** the implementer resumes,
   **Then** the check fails closed to today's refusal (no allowance is granted).

### Edge Cases

- The implementer of record is a generic placeholder actor (`implement-command`,
  `user`, `unknown`) → no allowance is granted from the projection (the existing
  generic-slot allowance is unchanged).
- No implementing event exists in the log → no allowance.
- The reviewer (slot occupant) itself runs implement → unchanged behaviour (compatible
  with the slot occupant, idempotent no-op).
- Actor identity recorded as a dict-shaped resolved binding vs a compact string → compared
  on the same tool key the existing check uses.
- A reviewer rejection made with `--force` and **no** `review_ref` is not a rework verdict;
  it counts as an implementing claim, so its actor becomes the implementer of record and the
  original implementer stays refused.
- Repeated rework cycles, including an `approved → in_progress` verdict → the implementer of
  record is still the last non-verdict implementing actor.
- The resume appends no lane event; the existing resume-refresh liveness annotation and its
  commit are unchanged.
- Out of scope: the consolidation preflight still reads the latest `→ in_progress` actor as the
  implementer (an advisory hollow-review warning that fails safe) — Follow-up: #5340.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Implementer of record resumes | As the implementer of record, I want `agent action implement` to resume an `in_progress` WP after a reviewer's `in_review → in_progress` rework verdict without `--force`, so that the review loop completes. | High | Open | [build] | no — RED on the base today (exit 1, `WorkPackageClaimConflict`) |
| FR-002 | Unrelated agent still refused | As a maintainer, I want an agent that is neither the slot occupant nor the implementer of record to stay refused, so that the allowance is not an ownership bypass. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture (same state, the implementer passes, a third tool is refused) |
| FR-003 | Fail closed on read failure | As a maintainer, I want a failure to read the latest implementer to leave today's refusal in place, so that an I/O fault never widens ownership. | Medium | Open | [build] | yes — paired with FR-001: the same fixture passes with the read restored |
| FR-004 | One ownership rule for every caller | As an orchestrator author, I want the shared implementation-start authority to carry the allowance, so that every implement entry point applies the same rule as `move-task`. | Medium | Open | [build] | no — asserted directly on the shared authority's `in_progress` arm |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra read on the happy path | The latest-implementer event read happens only when the slot-occupant check has already failed (0 extra reads for the unchanged paths). | Performance | Medium | Open |
| NFR-002 | Quality gates | New and changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero new suppressions; touched functions stay at complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse the canonical projection | Use `status.review_roles.latest_implementer_actor`; do not add a fourth "who implemented" projection. The wider unification is out of scope (Follow-up: #5340). | Technical | High | Open |
| C-002 | No `--force` in the loop | Neither the fix nor its tests may pass `--force` on any hop after the rejection. | Technical | High | Open |
| C-003 | Red-first | The regression test runs through the real `agent action implement` path and is RED on the planning base before the fix lands. | Process | High | Open |

### Key Entities

- **Slot occupant**: the actor on the latest status event for the WP (after a rejection, the reviewer).
- **Implementer of record**: the actor of the latest event into `claimed`/`in_progress` that is not a reviewer rework verdict and not a generic placeholder (`latest_implementer_actor`).
- **Reviewer rework verdict**: a move out of `for_review`/`in_review`/`approved` that carries a `review_ref`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's 5-step real-CLI reproduction exits 0 at step 5 with zero forced status events after the rejection (base: exit 1). — [build] · no-op passable: no
- **SC-002**: An agent on a third tool is refused at step 5 on the same fixture, writing zero status events. — [ratchet] · no-op passable: yes (paired with SC-001 on the same fixture)

## Assumptions

- The `--to planned` rejection route (control) keeps working unchanged; it re-claims through `planned → claimed → in_progress`.
