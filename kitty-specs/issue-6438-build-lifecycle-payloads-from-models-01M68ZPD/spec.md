# Mission Specification: Model-built payloads for the three post-mission lifecycle events

**Mission Branch**: `issue-6438-build-lifecycle-payloads-from-models`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6438 — "Build the MissionReopened, FollowUpRecorded and ReviewerSelfApproved events", on `spec-kitty/spec-kitty`, against `main` @ `6f73b2a98e`.

## Problem

Three lifecycle emitters in `src/specify_cli/status/lifecycle_events.py` write
their payload as a bare `dict`: `emit_mission_reopened`,
`emit_follow_up_recorded`, `emit_reviewer_self_approval`. Every other emitter in
the same file builds its payload through the canonical `spec_kitty_events`
model. Because these three do not, a payload field the published contract
rejects (`MissionReopenedPayload.reason` must be a non-empty string, for example)
reaches `status.events.jsonl` and is only detectable later, on the consumer
side — after the fact has been durably recorded.

All three run on live paths: `spec-kitty mission reopen`, `spec-kitty mission
follow-up`, and the reviewer-failure self-approval fallback in `tasks move`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A rejected payload fails before it is written (Priority: P1)

As a maintainer of the event ledger, I want every lifecycle emitter to build its
payload through the published contract model, so that a payload the contract
rejects never reaches disk.

**Why this priority**: This is the whole issue. Everything else is proof.

**Independent Test**: Call each of the three emitters with a field the model
rejects and confirm the call raises before any line is appended to the mission's
`status.events.jsonl`.

**Acceptance Scenarios**:

1. **Given** a completed mission and a re-open whose `reason` is an empty
   string, **When** `emit_mission_reopened` runs, **Then** the call raises a
   validation error and the lifecycle log still ends where it ended before the
   call.
2. **Given** a completed mission, **When** `emit_follow_up_recorded` is called
   with an empty `recorded_by`, **Then** the call raises a validation error and
   no row is appended.
3. **Given** a work package, **When** `emit_reviewer_self_approval` is called
   with an empty `failure_reason`, **Then** the call raises a validation error
   and no row is appended.

---

### User Story 2 - A valid emit is byte-identical to today's row (Priority: P1)

As an operator with existing ledgers, I want the three events to keep the shape
they have today, so that nothing downstream has to change and no historical line
is rewritten.

**Why this priority**: The change must be a validation ratchet, not a wire
change. A silent payload change would break readers and replay.

**Independent Test**: For each emitter, the persisted payload key set, key order
and values on a valid call equal what the emitter wrote before the change (the
canonical model's own dumped form).

**Acceptance Scenarios**:

1. **Given** any valid re-open, follow-up or self-approval, **When** the emitter
   returns, **Then** the persisted `payload` is exactly
   `Model(**fields).model_dump(mode="json", exclude_none=False)` for that
   model — including `null`-valued optional fields such as `cleared_merge`.
2. **Given** an existing `status.events.jsonl`, **When** the new code emits a
   further event, **Then** every pre-existing line is unmodified.

---

### User Story 3 - The write path and its guards are untouched (Priority: P2)

As a reviewer, I want the emitters' own pre-checks and the append primitive to
stay where they are, so this change is a payload-construction change and nothing
more.

**Why this priority**: The `#1926` completion guard and the `follow_up_type`
reference checks are named, tested invariants; a payload refactor must not move
or weaken them.

**Independent Test**: The existing suite for these emitters passes unchanged,
and `append_lifecycle_event` / `store.append_raw_rows_atomic` still appear as the
only write path.

**Acceptance Scenarios**:

1. **Given** a mission that has not completed, **When** a re-open or follow-up is
   emitted, **Then** `MissionNotCompletedError` is still raised with today's
   message and nothing is written.
2. **Given** `follow_up_type="pr"` with no `pr_number`, **When** the emitter
   runs, **Then** the emitter's own `ValueError` still fires (not a pydantic
   error), because the guard runs before construction.

### Edge Cases

- `cleared_merge=None` and an omitted `--reason` are different things: the model
  accepts a `None` snapshot, and rejects a missing or empty `reason`.
- A follow-up carrying both a commit and a PR number is two facts, recorded by
  two calls; the model does not need to reject it, and the emitter's
  discriminator keeps deciding.
- A `MissionReopened` may be appended more than once (append-each semantics);
  validation is per event, so a repeated valid re-open stays valid.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Model-built `MissionReopened` | As a ledger maintainer, I want `emit_mission_reopened` to construct `MissionReopenedPayload` so a re-open the contract rejects is refused at emit time. | High | Open | [build] | no — an empty `reason` is written to the log by the pre-change code |
| FR-002 | Model-built `FollowUpRecorded` | As a ledger maintainer, I want `emit_follow_up_recorded` to construct `FollowUpRecordedPayload` so a follow-up the contract rejects is refused at emit time. | High | Open | [build] | no — an empty `recorded_by` is written by the pre-change code |
| FR-003 | Model-built `ReviewerSelfApproval` | As a ledger maintainer, I want `emit_reviewer_self_approval` to construct `ReviewerSelfApprovalPayload` so a self-approval the contract rejects is refused at emit time. | High | Open | [build] | no — an empty `failure_reason` is written by the pre-change code |
| FR-004 | Persisted payload equals the model dump | As an operator, I want the persisted payload to be the model's own JSON dump, so the ledger row and the published contract cannot drift. | High | Open | [ratchet] | no — asserted per emitter against a freshly built model |
| FR-005 | Rejection lands before the write | As an operator, I want a rejected emit to leave the log byte-identical, so a failed emit is provably not a partial write. | High | Open | [build] | no — paired with the same-fixture positive control that the valid emit does append |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No regression in the emitter suites | The mission's blast-radius selection (the three emitter test modules plus `tests/specify_cli/status/`) passes with zero failures, and pre-existing tests in those modules are not edited to accommodate the change. | Reliability | High | Open |
| NFR-002 | One construction idiom | After the change, none of the three emitters assigns its payload from a bare dict literal; 3 of 3 build through a model and dump with `model_dump(mode="json", exclude_none=False)`. | Maintainability | High | Open |
| NFR-003 | Import hygiene | The models are imported inside the function body (`from spec_kitty_events.lifecycle import ...`), matching every other emitter in the file, so module import cost and the CLI's tolerant-import contract are unchanged. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Published models only | Payloads are built from `spec_kitty_events.lifecycle` / `spec_kitty_events.project_lifecycle` public models from the pinned `spec-kitty-events>=11.3.0,<12`. No private symbol is imported (`tests/architectural/test_events_tracker_public_imports.py`). | Technical | High | Open |
| C-002 | Envelope and write path unchanged | `_build_envelope`, `append_lifecycle_event`, `persist_lifecycle_event_local` and `store.append_raw_rows_atomic` are not modified; event type constants, `schema_version` and dedup keys are unchanged. | Technical | High | Open |
| C-003 | Out of scope: retiring the hosted builder | The issue's third checkbox (retiring `build_saas_lifecycle_queue_event` / `_canonical_lifecycle_payload_for_saas`) was completed by #6607. This mission does not re-delete anything, and the issue is closed with that item recorded as already done. | Business | High | Open |
| C-004 | No gate weakened | No test is skipped, xfailed, loosened or removed to make this pass; no lint/type/arch gate is suppressed. | Technical | High | Open |

### Key Entities

- **`MissionReopenedPayload`**: `spec_kitty_events.lifecycle`, `frozen`,
  `extra="forbid"`; `mission_id`, `mission_slug`, `reason` (non-empty),
  `reopened_by`, `reopened_at`, optional `cleared_merge` snapshot.
- **`FollowUpRecordedPayload`**: `spec_kitty_events.lifecycle`, `frozen`,
  `extra="forbid"`; `mission_id`, `mission_slug`, `follow_up_type`
  (`commit`|`pr`), optional `commit_sha` / `pr_number`, `recorded_by`,
  `recorded_at`.
- **`ReviewerSelfApprovalPayload`**: `spec_kitty_events.project_lifecycle`,
  `frozen`, `extra="forbid"`; `mission_slug`, `wp_id`, `implementing_actor`,
  `intended_reviewer`, `failure_reason`, `fallback_approved`, `timestamp`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the three emitters rejects a model-invalid field before appending, proven by a test that also proves the same fixture appends on valid input. — [build] · no-op passable: no
- **SC-002**: 3 of 3 emitters' persisted payloads equal their model dump, asserted key-for-key including `null` optionals. — [ratchet] · no-op passable: no
- **SC-003**: The pre-existing emitter and post-mission suites pass with zero modified assertions. — [ratchet] · no-op passable: no
- **SC-004**: Issue #6438's acceptance items 1 and 2 are answered in the PR, and item 3 is recorded as delivered by #6607. — [build] · no-op passable: no
