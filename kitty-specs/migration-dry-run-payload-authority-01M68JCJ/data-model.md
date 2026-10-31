# Data Model — Migration dry-run payload authority

Scope: the values this mission touches. No persisted schema changes; the only
on-disk reads are existing `status.events.jsonl` rows.

## Entity: `StatusEvent` (existing, unchanged)

The local canonical lane-transition row. Read-only input for the dry-run.

| Field | Type | Role in this mission |
| --- | --- | --- |
| `event_id` | ULID `str` | Envelope `event_id`; correlation id seed |
| `mission_slug` | `str` | payload field |
| `mission_id` | `str \| None` | payload field — **now carried** (was dropped) |
| `wp_id` | `str` | payload field; envelope `aggregate_id` |
| `from_lane` | `Lane` | payload field, `str()`-rendered; may be overridden (`in_progress -> in_review` becomes `for_review`) |
| `to_lane` | `Lane` | payload field, `str()`-rendered |
| `at` | ISO-8601 `str` | envelope `timestamp` |
| `actor` | `str \| dict` | payload field, passed verbatim (`decode_actor` already applied) |
| `force` | `bool` | payload field |
| `execution_mode` | `"worktree" \| "direct_repo"` | payload field |
| `reason` | `str \| None` | payload field, explicit `null` kept |
| `reason_source` | `str \| None` | **not** a payload field (local-only provenance) |
| `review_ref` | `str \| None` | payload field, explicit `null` kept |
| `evidence` | local `DoneEvidence \| None` | payload field via `.to_dict()`; may be overridden by historical synthesis |
| `review_result` | `ReviewResult \| None` | **not** a payload field (local-only) |
| `policy_metadata` | `dict \| None` | **not** a payload field (local-only) |

## Entity: `WPStatusChanged` payload (owner: `spec_kitty_events.status.StatusTransitionPayload`)

The contract-shaped dict inside the TeamSpace replay envelope.

| Field | Type | Required | Wire-shape rule |
| --- | --- | --- | --- |
| `mission_slug` | `str` (min 1) | yes | always present |
| `mission_id` | `str \| None` | no | present iff set |
| `wp_id` | `str` (min 1) | yes | always present |
| `from_lane` | `Lane \| None` | no | present iff set (`str` accepted, aliases resolved by the model) |
| `to_lane` | `Lane` | yes | always present |
| `actor` | `str \| dict` (non-empty) | yes | always present |
| `force` | `bool` | yes (defaults `False`) | always present |
| `reason` | `str \| None` | no | **explicit `null` kept** |
| `execution_mode` | `ExecutionMode` | yes | always present |
| `review_ref` | `str \| None` | no | **explicit `null` kept** |
| `summary` | `str \| None` | no | never produced locally (display-only producer input) |
| `evidence` | `DoneEvidence \| None` | no | **explicit `null` kept** |

### Invariants

1. **Coverage**: every model field is either mapped from a `StatusEvent`
   attribute or listed as producer-supplied-only (`summary`). Enforced by test.
2. **Validation at construction**: `force=True` requires a non-empty `reason`;
   `to_lane in {approved, done}` requires `evidence`; `DoneEvidence.repos` has at
   least one entry. A violation raises `pydantic.ValidationError`.
3. **Null policy**: `reason`, `review_ref`, `evidence` survive as `null`; no
   other unset optional appears.
4. **Local-only fields never cross**: `policy_metadata`, `review_result`,
   `reason_source` cannot appear (the model is `extra="forbid"`, and the builder
   never passes them).
5. **Determinism**: the payload for a given `StatusEvent` is a pure function of
   the event plus the dry-run's documented overrides — no clock, no environment.

### Validation rules applied where

| Layer | Owner | What it proves |
| --- | --- | --- |
| Pydantic model construction | `status.wire_payload` | field types, required fields, actor/force/evidence business rules |
| `validate_event(..., "WPStatusChanged")` | `migration.mission_state` (unchanged) | JSON-schema conformance plus the shared semantic transition rules |

## Entity: dry-run envelope (existing, unchanged shell)

`_TeamspaceEnvelope` keeps its 15 fields. Only `payload` construction changes;
`event_id`, `aggregate_id`/`aggregate_type`, `timestamp`, `lamport_clock`,
correlation seed and `build_id`/`node_id` are unchanged. `envelope_sha256` is
recomputed from the (now model-built) payload, so hashes for rows carrying
`mission_id` change deterministically.
