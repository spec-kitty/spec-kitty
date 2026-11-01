# Discovery — migration dry-run payload authority (#6449)

## Decision 1: one CORE builder, exported on the `status` facade

**Decision**: add `build_wp_status_changed_payload(...)` to a new CORE module
`src/specify_cli/status/wire_payload.py`, constructed through
`spec_kitty_events.status.StatusTransitionPayload` and shaped with
`specify_cli.core.payload_shaping.apply_keep_none_fields`, then re-export it from
`specify_cli.status.__all__`. `migration/mission_state.py` imports it from the
facade only.

**Rationale / evidence**:

- The in-repo precedent for a canonical wire-payload builder is
  `src/specify_cli/core/mission_payload.py::build_mission_created_payload`
  (#2270): model construction + `apply_keep_none_fields` + a named
  `_KEEP_NONE_FIELDS` allowlist. Same shape, same layer discipline.
- `tests/architectural/test_status_module_boundary.py` (SR-2) forbids any module
  outside `specify_cli.status` importing a `specify_cli.status.*` submodule, so a
  new symbol is reachable from `migration/` only via the facade `__all__`.
- `tests/architectural/test_no_dead_symbols.py` requires a non-test `src/` caller
  for a public name; the migration call site is that caller.
- `tests/architectural/test_integration_boundary.py`: the builder must not import
  `sync`/`tracker`/hosted; `apply_keep_none_fields` is CORE and
  `spec_kitty_events` is a shared contract package, so the boundary holds.

## Decision 2: wire-shape policy — keep three nulls, add `mission_id`

**Decision**: `_KEEP_NONE_FIELDS = ("reason", "review_ref", "evidence")`;
everything else unset is absent. `mission_id` therefore appears exactly when the
event carries one.

**Rationale / evidence**:

- The dry-run emits `schema_version "3.0.0"` envelopes, and the package's
  canonical 3.0.0 `WPStatusChanged` conformance case
  (`spec_kitty_events/producer_contract/fixtures/upcast/cases/conformance/mission_lifecycle.WPStatusChanged.136.json`)
  carries explicit `"evidence": null, "reason": null, "review_ref": null` and no
  `mission_id` key. Dropping the nulls would be a wire change.
- A real local transition row (`StatusEvent.to_dict()` via
  `status.store.serialize_event_line`) also always carries those three keys, and
  emits `mission_id` only when populated. That row is the durable authority the
  dry-run replays, so parity with it is the pin.
- Today the dry-run silently drops `mission_id` although modern repaired rows
  always carry it (`tests/migration/test_mission_state_repair.py` asserts
  `row["mission_id"] == meta["mission_id"]`). Carrying it is the parity fix.
- `summary` stays absent: `StatusEvent` has no summary, and the model field is
  display-only (spec-kitty-events#4327). `policy_metadata`, `review_result` and
  `reason_source` are local-only and are dropped by the model boundary
  (`extra="forbid"` is on the model, so they must simply not be passed).

## Decision 3: parity oracle for the test

**Decision**: the red-first test emits a **real** transition through the public
status API into a mission log, runs `teamspace_dry_run()`, and compares the
synthesized `payload` to the canonical payload rendered from the *real event*
(the durable row), byte for byte via `json.dumps(sort_keys=True)`. A second
assertion proves the dry-run actually calls the facade builder by substituting it
on the migration module.

**Rationale**: a test that only compares the builder to itself is tautological.
The real row is written by an independent production path
(`emit_status_transition` -> store -> `serialize_event_line`), so it can fail.

## Decision 4: model rejection stays a report, not raise

**Decision**: the migration call catches `pydantic.ValidationError` from the
builder and appends the existing `PAYLOAD_INVALID` error record (with
`model_violations`), then continues to the next event.

**Rationale**: today a contract-invalid payload is reported at the `validate_event`
layer; constructing through the model moves that rejection earlier. Without the
catch, one bad row would abort the whole dry-run — a behaviour regression the
`PAYLOAD_INVALID` contract exists to prevent.

## Open questions (resolved during this discovery)

- *Is the issue stale after the 2026-10-27 park?* No: `spec-kitty-events#92`
  closed 2026-10-27 and the pin is `>=11.3.0,<12` (installed 11.3.0) with
  `StatusTransitionPayload` present.
- *Does the fan-out path (`status/emit._status_fan_out` ->
  `adapters.fire_status_fanout`) also need to route through the new builder?*
  Out of scope: it forwards structured kwargs and `WPStatusChangeMetadata` to a
  transport handler that open-core no longer registers (#6164). Changing that
  seam is a separate contract change and is not needed to give the dry-run a
  single authority. Noted in `## Deferred`.
