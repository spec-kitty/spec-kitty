# Mission Specification: Migration dry-run payload authority

**Mission Branch**: `issue-6449-migration-dry-run-payload-authority`
**Created**: 2026-10-31
**Status**: Draft
**Input**: "Build the migration dry-run WPStatusChanged through StatusTransitionPayload" (spec-kitty/spec-kitty#6449); guidance: "The migration dry-run hand-builds a `WPStatusChanged` event instead of going through the canonical `StatusTransition` builder — a second event authority. Route it through the builder and pin byte parity with a real transition."

## Grounding (recorded before scoping)

- **Reproduces on current `main`** (`35318ef51c`): `src/specify_cli/migration/mission_state.py::_status_event_to_teamspace_envelope` (payload literal at ~1317-1328) assembles the dry-run `WPStatusChanged` payload as a plain `dict`, carrying a `# canonical-producer-exempt: #1198` marker.
- **Not superseded**: `git log -S "StatusTransitionPayload" -- src/specify_cli/migration/` is empty; no PR references the issue; nothing in the changelog covers it.
- **Parking gate cleared**: the 2026-10-27 note parked this behind `spec-kitty-events#92`, which **closed 2026-10-27**; the repo pins `spec-kitty-events>=11.3.0,<12` (installed 11.3.0), which ships `StatusTransitionPayload` including `mission_id` and `summary`.
- **Revised rationale** (issue triage asked for it): the payload *is* validated today — envelope at `~1048`, payload conformance via `validate_event` at `~1059` — so this is **construction-time authority hygiene**, not an unvalidated live write. What is missing is that the payload is never *constructed* by the contract model, so a hand-built dict can drift from the model (missing/renamed/extra key) and only surfaces later as a `PAYLOAD_INVALID` report.
- **Domain term**: "dry-run payload" here means the `payload` member of the TeamSpace replay envelope (`schema_version 3.0.0`) that `--teamspace-dry-run` synthesizes per `WPStatusChanged` row; it is not the local `status.events.jsonl` row itself.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One authority for the dry-run `WPStatusChanged` payload (Priority: P1)

A maintainer running `spec-kitty doctor mission-state --teamspace-dry-run` gets a synthesized TeamSpace envelope whose `WPStatusChanged` payload is built by the shared contract model, so the dry-run can no longer drift from what a real transition writes, and an unrepresentable row is reported as an error instead of silently shaping a bespoke dict.

**Why this priority**: it is the whole issue. A second hand-rolled authority for an event shape is exactly the defect class the canonical-producer rule (C-007) exists to close; the dry-run is the last production site that hand-shapes this payload.

**Independent Test**: emit a real transition through the public status API into a mission log, run `teamspace_dry_run()` over that repo, and assert the synthesized `payload` is byte-identical to the canonical payload for the same event; plus assert the builder is the code path the dry-run calls.

**Acceptance Scenarios**:

1. **Given** a mission log containing a real `claimed -> in_progress` transition, **When** the dry-run synthesizes its envelope, **Then** the envelope `payload` equals the canonical `StatusTransitionPayload` rendering of that event, byte for byte (`json.dumps(..., sort_keys=True)`), including the event's `mission_id`.
2. **Given** the dry-run path, **When** it constructs the payload, **Then** construction goes through the canonical builder exported by `specify_cli.status` (proven by substituting the builder on the migration module and observing it is called), and no payload dict literal remains at the call site.
3. **Given** a row whose evidence cannot be represented by the contract model (e.g. `done` evidence with no repos and no review), **When** the dry-run runs, **Then** it reports `PAYLOAD_INVALID` for that row and stays non-raising, exactly as today.
4. **Given** the historical rewrites the dry-run owns (the `in_progress -> in_review` `for_review` alias and approval/done evidence synthesis), **When** those rows are synthesized, **Then** the rewrites still happen before the payload is built and the result still validates.

### Edge Cases

- A row carrying `mission_id` must now surface it in the payload (it was silently dropped); a legacy row without `mission_id` must not gain a `null` key.
- `reason`, `review_ref` and `evidence` must stay present as explicit `null` when unset — the 3.0.0 transport fixture and real rows both carry them, so dropping them would be a wire change.
- `summary` must not appear: local transitions never carry one, and the model field is display-only.
- `policy_metadata`, `review_result` and `reason_source` are local-only `StatusEvent` fields with no counterpart on the payload model; they must be dropped by construction, not passed through.
- A model rejection must never abort the whole dry-run; it is one row's error.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Payload built by the contract model | As a maintainer, I want the dry-run payload constructed through `StatusTransitionPayload` so that an unrepresentable payload fails at construction, not at conformance time. | High | Open | [build] | no — a no-op leaves the dict literal in place |
| FR-002 | Single authority, exemption retired | As a maintainer, I want the hand-built payload dict and its `canonical-producer-exempt` marker gone from the migration module so that there is one authority for the shape. | High | Open | [build] | no |
| FR-003 | Wire shape preserved and completed | As a downstream consumer, I want the payload to keep the explicit nulls for `reason`/`review_ref`/`evidence` and to carry `mission_id` when the event has one, so the dry-run matches a real transition instead of dropping a canonical field. | High | Open | [build] | no |
| FR-004 | Model rejection is a reported error | As an operator, I want a row the model rejects reported as `PAYLOAD_INVALID` (non-raising) so the dry-run keeps reporting every mission instead of crashing on one row. | High | Open | [ratchet] | yes — paired with FR-001's positive control on the same fixture (a valid row builds and validates) |
| FR-005 | Parity pinned by test | As a reviewer, I want a test that pins dry-run payload bytes against a real transition's canonical payload so the two authorities cannot silently diverge again. | High | Open | [build] | no |
| FR-006 | Historical rewrites unchanged | As an operator, I want the `for_review` alias and approval/done evidence synthesis to still apply before construction so historical rows keep synthesizing. | Medium | Open | [ratchet] | yes — paired with the same-fixture assertion that a non-rewritten row is untouched |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Determinism preserved | `tests/migration/test_teamspace_migration_rehearsal.py` (cross-clone byte determinism) passes unchanged; two dry-runs over the same fixture produce identical `to_dict()` output. | Reliability | High | Open |
| NFR-002 | No new dependencies | No new runtime or test dependency; the `spec-kitty-events` floor stays `>=11.3.0,<12`. | Maintainability | High | Open |
| NFR-003 | Changed-line coverage | Diff-cover on changed lines stays at or above 90%. | Testability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical producer (C-007) | The payload must be constructed through the `spec_kitty_events` pydantic model; no second hand-shaped dict may remain. | Technical | High | Open |
| C-002 | CORE-only builder | The builder lives in the CORE `specify_cli.status` layer and imports nothing from INTEGRATION (`sync`/`tracker`/hosted), preserving the CORE→INTEGRATION boundary. | Technical | High | Open |
| C-003 | Facade boundary | Consumers reach it through `specify_cli.status.__all__`; no external module imports a status submodule directly (SR-2). | Technical | High | Open |
| C-004 | No wire change for existing fields | Any payload change must be justified against the 3.0.0 transport fixture and the real row; no field may be silently added, renamed or removed. | Technical | High | Open |

### Key Entities

- **`WPStatusChanged` payload**: the contract-shaped `dict` inside the TeamSpace replay envelope; owned by `spec_kitty_events.status.StatusTransitionPayload`.
- **`StatusEvent`**: the local canonical transition row (`status.events.jsonl`); its durable JSON is the parity oracle.
- **Dry-run envelope**: the `_TeamspaceEnvelope` shell (event id, type, aggregate, lamport clock, project/team context) whose `payload` this mission builds through the model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A dry-run over a repo with a real emitted transition yields a `payload` byte-identical to the canonical payload for that event, asserted by test. — [build] · no-op passable: no
- **SC-002**: `python scripts/lint_canonical_producers.py --paths src/ scripts/ tests/ --baseline scripts/canonical_producer_lint_baseline.txt` reports no new violation, and the migration module no longer needs its `canonical-producer-exempt` marker. — [build] · no-op passable: no
- **SC-003**: The existing dry-run/repair suites (`tests/migration/`, the mission-state doctor CLI tests, the fidelity e2e) pass with no golden edits beyond the intentional `mission_id` addition. — [ratchet] · no-op passable: no
- **SC-004**: A model-rejected row produces a `PAYLOAD_INVALID` report entry and the run still completes (exit-1 report, no traceback). — [ratchet] · no-op passable: yes — guarded by the same-fixture valid-row positive control.
