# Contract — the three lifecycle payloads at the emit boundary

Scope: what `specify_cli.status.lifecycle_events` promises about the `payload`
object of a `MissionReopened`, `FollowUpRecorded` or `ReviewerSelfApproval` row
in `status.events.jsonl`.

## C-1 — A persisted payload is a published model's dump

For a successful emit, the persisted `payload` equals

```
Model(**fields).model_dump(mode="json", exclude_none=False)
```

where `Model` is `MissionReopenedPayload` / `FollowUpRecordedPayload`
(`spec_kitty_events.lifecycle`) or `ReviewerSelfApprovalPayload`
(`spec_kitty_events.project_lifecycle`).

Consequences a consumer may rely on:

- the key set is exactly the model's field set — no extras (`extra="forbid"`);
- optional fields appear as `null`, never omitted (`exclude_none=False`);
- key order on disk is the row writer's, not the model's: `append_raw_rows_atomic`
  serializes with `sort_keys=True`, so a persisted payload's keys are
  alphabetical. Compare payloads by key set and values, never by order.
- every `str` field is non-empty except where the model declares `Optional`.

## C-2 — A rejected payload is not written

If model construction raises, the function raises before
`append_lifecycle_event` is reached; the log's byte length and line count are
unchanged. There is no partial write and no "written then repaired" state.

The exception type is `pydantic.ValidationError`, which is a `ValueError`.

## C-3 — Emitter guards win over model validation

These emitter-level checks run *before* construction and keep their current
exception type and message:

| Emitter | Guard | Raises |
| --- | --- | --- |
| `emit_mission_reopened` | mission has completed/merged (`#1926`) | `MissionNotCompletedError` |
| `emit_follow_up_recorded` | mission has completed/merged (`#1926`) | `MissionNotCompletedError` |
| `emit_follow_up_recorded` | `follow_up_type` is `commit`\|`pr` and its reference is present | `ValueError` |

A caller that relied on those messages sees no change.

## C-4 — Nothing else about the row changes

`event_type`, `aggregate_id`, `aggregate_type`, `schema_version` (`5.0.0`),
`timestamp`, `project_uuid`, `project_slug`, the dedup keys, and the append
primitive (`append_lifecycle_event` → `store.append_raw_rows_atomic`) are
unchanged. Historical lines are never rewritten.

## Out of contract

- A `ValidationError` raised *by a programmatic caller* passes through unrendered.
  The CLI is not obliged to catch it: `spec-kitty mission reopen` validates its own
  required `--reason` first and refuses with `reason_required`, so an operator does
  not meet the traceback on that path. Any other caller that constructs an invalid
  payload gets the exception, which is the point.
