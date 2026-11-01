# Work Packages: Migration dry-run payload authority

**Inputs**: Design documents from `kitty-specs/migration-dry-run-payload-authority-01M68JCJ/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/wp-status-changed-payload.md, quickstart.md
**Mission**: #6449 — build the dry-run `WPStatusChanged` payload through `StatusTransitionPayload`

**Organization**: Two work packages. WP01 delivers the CORE builder and its
facade export; WP02 rewires the dry-run call site, pins byte parity against a real
transition, and records the changelog entry.

**Prompt Files**: `tasks/WP01-canonical-wp-status-changed-payload-builder.md`,
`tasks/WP02-dry-run-call-site-and-parity-pin.md`.

## Subtask Format

`Txxx` rows are reference rows, never checkboxes. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

Single project: `src/specify_cli/...`, `tests/...`, `docs/changelog/CHANGELOG.md`.

---

## Work Package WP01: Canonical `WPStatusChanged` payload builder (Priority: P0)

**Goal**: One CORE constructor for the `WPStatusChanged` payload, built through
`spec_kitty_events.status.StatusTransitionPayload`, exported on the
`specify_cli.status` facade, with a test-enforced field-coverage ratchet.
**Independent Test**: `uv run pytest tests/status/test_wire_payload.py -q` passes,
and the builder's output for a representative event equals the documented key
set and null policy.
**Prompt**: `tasks/WP01-canonical-wp-status-changed-payload-builder.md`
**Requirement Refs**: FR-001, FR-003, C-001, C-002, C-003

### Included Subtasks

T001 [P] Unit test: canonical key set and null policy in `tests/status/test_wire_payload.py`
T002 [P] Unit test: model-field coverage ratchet against `StatusTransitionPayload.model_fields`
T003 Implement `src/specify_cli/status/wire_payload.py` (`build_wp_status_changed_payload`, `build_status_event_payload`)
T004 Promote the builder onto `src/specify_cli/status/__init__.py`'s `__all__`
T005 [P] Unit test: model rejection raises (force without reason, approved without evidence) and an unknown override key is refused

### Implementation Notes

- Mirror `src/specify_cli/core/mission_payload.py::build_mission_created_payload`:
  construct the model, then `apply_keep_none_fields(model, keep_none_fields=...)`.
- `_KEEP_NONE_FIELDS = ("reason", "review_ref", "evidence")`;
  `_PRODUCER_SUPPLIED_FIELDS = frozenset({"summary"})`; `_EVENT_FIELD_ATTRS` maps
  each remaining model field to its `StatusEvent` attribute.
- `str()` the lanes, `event.evidence.to_dict() if event.evidence else None` for
  evidence; `actor` passes through as `str | dict`.
- Overrides are validated against the model's field names and raise `ValueError`
  on an unknown key.

### Parallel Opportunities

T001/T002/T005 are separate test bodies and can be authored together; T003 is the
implementation they drive.

### Dependencies

- None.

### Risks & Mitigations

- Facade export breaks SR-2 or the dead-symbol gate → export only what the
  migration call site uses, and keep the module free of INTEGRATION imports.
- Null-policy drift from the 3.0.0 fixture → T001 pins the exact key set.

---

## Work Package WP02: Dry-run call site and byte-parity pin (Priority: P0) 🎯 MVP

**Goal**: `_status_event_to_teamspace_envelope` builds its payload only through
the facade builder, keeps the historical overrides, reports a model rejection as
`PAYLOAD_INVALID` instead of raising, and byte parity with a real transition is
pinned by a test that can fail.
**Independent Test**: emit a real transition into a mission log, run
`teamspace_dry_run()`, and observe the synthesized payload equals the canonical
payload rendered from that event's durable row byte for byte.
**Prompt**: `tasks/WP02-dry-run-call-site-and-parity-pin.md`
**Requirement Refs**: FR-002, FR-004, FR-005, FR-006, C-004, NFR-001
**Depends on**: WP01

### Included Subtasks

T006 Red-first: `tests/migration/test_mission_state_teamspace_payload_authority.py` — parity with a real emitted transition, builder-is-called proof, rejected-row report
T007 Rewire `_status_event_to_teamspace_envelope` onto the facade builder and delete the payload literal plus the `canonical-producer-exempt` marker
T008 Catch `pydantic.ValidationError` in the dry-run loop and append the `PAYLOAD_INVALID` record (mapped `field`/`message`/`violation_type`)
T009 Run the targeted suites, the canonical-producer lint and the architectural gates; record results
T010 Add the `[Unreleased]` changelog entry for #6449

### Implementation Notes

- Historical rewrites stay in the migration module and are passed as overrides:
  the `in_progress -> in_review` `for_review` alias and the approval/done evidence
  synthesis.
- The parity assertion compares `json.dumps(payload, sort_keys=True)` on both
  sides; the expected side is derived from the real event, not from the builder.
- Commit order: T006 (red) first, then T007/T008 (green), then T010.

### Parallel Opportunities

None — the call-site rewrite and its tests are one lane.

### Dependencies

- WP01 (the builder and its facade export).

### Risks & Mitigations

- A tautological parity test (builder compared to itself) → oracle is the durable
  row written by `emit_status_transition`.
- Losing the non-raising rejection contract → T008's test runs a rejected row and
  a valid row on the same fixture and asserts both are reported.
