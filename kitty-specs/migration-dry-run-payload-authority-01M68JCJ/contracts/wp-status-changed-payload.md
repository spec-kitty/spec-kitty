# Contract: `WPStatusChanged` envelope payload

Owner of the shape: `spec_kitty_events.status.StatusTransitionPayload` (external
contract package, pinned `>=11.3.0,<12`).
Producer in this repository: `specify_cli.status.build_status_event_payload`
(CORE), reached through `specify_cli.status.__all__`.
Consumer in this mission: `specify_cli.migration.mission_state._status_event_to_teamspace_envelope`
(TeamSpace replay dry-run).

## Scope

This contract covers the `payload` member of a TeamSpace replay envelope with
`event_type == "WPStatusChanged"` and `schema_version == "3.0.0"`, as synthesized
by `spec-kitty doctor mission-state --teamspace-dry-run`. It does not cover the
envelope shell (see `_TeamspaceEnvelope`) and does not cover the local
`status.events.jsonl` row shape (`status.store.serialize_event_line`).

## Key set

Exactly these keys may appear; no others:

```
mission_slug, mission_id, wp_id, from_lane, to_lane, actor, force,
reason, execution_mode, review_ref, summary, evidence
```

Presence rules:

| Key | Presence |
| --- | --- |
| `mission_slug`, `wp_id`, `to_lane`, `actor`, `force`, `execution_mode` | always |
| `mission_id`, `from_lane`, `summary` | only when the value is set (`summary` is never set by this producer) |
| `reason`, `review_ref`, `evidence` | always — explicit `null` when unset |

Byte-level expectations pinned by the 3.0.0 conformance fixture
(`mission_lifecycle.WPStatusChanged.136.json`) and by a real local row.

## Validation

1. Construction goes through `StatusTransitionPayload` (`extra="forbid"`,
   `frozen=True`), so an unknown or misspelled key is a construction error, not a
   silent extra.
2. Model business rules: `force=True` needs a non-empty `reason`; `approved` /
   `done` need `evidence`; `DoneEvidence.repos` needs at least one entry.
3. `validate_event(payload, "WPStatusChanged")` still runs afterwards for
   JSON-schema conformance and the shared semantic transition rules.
4. A construction failure is **reported**, not raised out of the dry-run: the
   report gains a `PAYLOAD_INVALID` entry carrying `mission_slug`, `event_id` and
   `model_violations` (`field`, `message`, `violation_type`).

## Parity guarantee

For a `StatusEvent` whose dry-run path applies no historical override, the
payload must be byte-identical (`json.dumps(..., sort_keys=True)`) to the payload
rendered from that event's durable `status.events.jsonl` row. Pinned by
`tests/migration/test_mission_state_teamspace_payload_authority.py`.

## Historical overrides (documented exceptions, owned by the migration module)

| Override | When | Why |
| --- | --- | --- |
| `from_lane -> for_review` | event is `in_progress -> in_review` | older local logs skipped the explicit `for_review` queue lane |
| `evidence` synthesized | `to_lane` is `approved` or `done` | the 5.0.0 event contract requires repo + review evidence, which historical rows may lack |

This is the complete override list. Any further divergence between the dry-run
payload and a real row is a defect, not an override.

## One documented normalization

`evidence` is emitted as the contract model renders it: `repos` and `review` are
preserved, and `verification` is always materialized (an empty list when the row
carried none, which a local `DoneEvidence.to_dict()` omits). That is the shape
every model-built `WPStatusChanged` payload already has, so it is a
normalization to the contract — not an override, and not a hand-shaped
divergence. Pinned by `test_done_evidence_rides_as_the_contract_shape`.

## Drift ratchet

`status.wire_payload._EVENT_FIELD_ATTRS` ∪ `_PRODUCER_SUPPLIED_FIELDS` must equal
`set(StatusTransitionPayload.model_fields)`. A test asserts it, so a new field on
the contract model fails CI until the producer maps it (or declares it
producer-supplied) — the failure mode that let the dry-run silently drop
`mission_id`.
