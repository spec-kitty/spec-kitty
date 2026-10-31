# Data Model — the three post-mission lifecycle payloads

The mission changes no stored schema. It makes three already-published payload
models the construction authority for three already-written event types, so the
"data model" here is the contract each emitter must now satisfy.

All three models live in `spec-kitty-events` (`frozen=True`, `extra="forbid"`),
pinned by `pyproject.toml` as `spec-kitty-events>=11.3.0,<12`.

## MissionReopenedPayload — `spec_kitty_events.lifecycle`

| Field | Type | Required | Constraint | Today's dict |
| --- | --- | --- | --- | --- |
| `mission_id` | `str` | yes | non-empty | same |
| `mission_slug` | `str` | yes | non-empty | same |
| `reason` | `str` | yes | non-empty (`min_length=1`) | same key, unvalidated |
| `reopened_by` | `str` | yes | non-empty | same |
| `reopened_at` | `str` | yes | non-empty ISO-8601 | same |
| `cleared_merge` | `dict[str, Any] \| None` | no | may be `null` | same |

- **Producer**: `emit_mission_reopened` (`status/lifecycle_events.py`), called by `spec-kitty mission reopen`.
- **Invariants**: append-each, never deduped — every re-open is a distinct fact.
- **Rejected cases the emitter must now refuse**: empty/`None` `reason`,
  empty `reopened_by`, empty `mission_id`/`mission_slug`/`reopened_at`.

## FollowUpRecordedPayload — `spec_kitty_events.lifecycle`

| Field | Type | Required | Constraint | Today's dict |
| --- | --- | --- | --- | --- |
| `mission_id` | `str` | yes | non-empty | same |
| `mission_slug` | `str` | yes | non-empty | same |
| `follow_up_type` | `Literal["commit", "pr"]` | yes | discriminator | same (already guarded) |
| `commit_sha` | `str \| None` | no | non-empty when present | same |
| `pr_number` | `int \| None` | no | — | same |
| `recorded_by` | `str` | yes | non-empty | same key, unvalidated |
| `recorded_at` | `str` | yes | non-empty ISO-8601 | same |

- **Producer**: `emit_follow_up_recorded`, called by `spec-kitty mission follow-up`.
- **Invariants**: idempotent on `(mission_id, commit_sha | pr_number)`; the
  emitter's own guard already rejects a `commit` without `commit_sha` and a `pr`
  without `pr_number`, and stays ahead of model construction.
- **Rejected cases the emitter must now refuse for `recorded_by` /
  `recorded_at` / `mission_id`**, i.e. fields only the model checks.

## ReviewerSelfApprovalPayload — `spec_kitty_events.project_lifecycle`

| Field | Type | Required | Constraint | Today's dict |
| --- | --- | --- | --- | --- |
| `mission_slug` | `str` | yes | non-empty | same |
| `wp_id` | `str` | yes | non-empty | same |
| `implementing_actor` | `str` | yes | non-empty | same |
| `intended_reviewer` | `str` | yes | non-empty | same |
| `failure_reason` | `str` | yes | non-empty | same key, unvalidated |
| `fallback_approved` | `bool` | yes | defaults to `True` in the emitter | same |
| `timestamp` | `str` | yes | non-empty | same |

- **Producer**: `emit_reviewer_self_approval`, called by the reviewer-failure
  fallback in `tasks move`.
- **Invariants**: idempotent on
  `(mission_slug, wp_id, implementing_actor, intended_reviewer, failure_reason)`.
- **Rejected cases the emitter must now refuse**: an empty `failure_reason`, an
  empty `implementing_actor`/`intended_reviewer`, a non-bool `fallback_approved`.

## Persisted envelope (unchanged)

Every emitted event keeps the envelope produced by `_build_envelope`:

```json
{
  "event_id": "<ULID>",
  "event_type": "MissionReopened | FollowUpRecorded | ReviewerSelfApproval",
  "aggregate_id": "<mission_id | wp_id>",
  "aggregate_type": "Mission | WorkPackage",
  "schema_version": "5.0.0",
  "timestamp": "<ISO-8601 UTC>",
  "payload": { "<the model dump>" },
  "project_uuid": null,
  "project_slug": null
}
```

## State transitions

None. These are post-mission observational facts; no lane moves, no status
projection changes. `MissionReopened` is consumed by
`status/lifecycle.py::derive_mission_lifecycle` to make a merged mission
actionable again; `FollowUpRecorded` and `ReviewerSelfApproval` are recorded
facts only.

## Historical data

Existing `status.events.jsonl` lines are never rewritten. Because each model
accepts exactly the fields and values the emitters already produce, a valid emit
before and after this change serialises to the same JSON.
