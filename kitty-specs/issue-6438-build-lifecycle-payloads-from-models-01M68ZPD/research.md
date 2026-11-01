# Discovery — #6438 build the three post-mission lifecycle payloads from the events models

Mission: `issue-6438-build-lifecycle-payloads-from-models-01M68ZPD`
Base: `origin/main` @ `6f73b2a98e`

## The issue, grounded on current main

`src/specify_cli/status/lifecycle_events.py` is the canonical local writer for
`status.events.jsonl` / `.kittify/canonical-events.jsonl`. Some of its emitters
already build their payload through the canonical `spec_kitty_events` pydantic
model and dump it (`emit_mission_created_local` → `build_mission_created_payload`,
`emit_artifact_phase_local` → `Specify/Plan/Tasks{Started,Completed}Payload`,
`emit_wp_created_local` → `WPCreatedPayload`). Three do not:

| Emitter | Line | Payload built as | Canonical model (installed 11.3.0) |
| --- | --- | --- | --- |
| `emit_reviewer_self_approval` | `:869` | plain `dict` | `spec_kitty_events.project_lifecycle.ReviewerSelfApprovalPayload` |
| `emit_mission_reopened` | `:924` | plain `dict` | `spec_kitty_events.lifecycle.MissionReopenedPayload` |
| `emit_follow_up_recorded` | `:987` | plain `dict` | `spec_kitty_events.lifecycle.FollowUpRecordedPayload` |

The three are reached from real production callers — `mission_type.py:1566`
(`spec-kitty mission reopen`), `mission_type.py:1699` (`spec-kitty mission
follow-up`), `tasks_move_task_executor.py:603` (self-approval fallback) — so the
gap is on a live write path, not a dead one.

## Acceptance item 3 is already closed upstream of this mission

The issue's third checkbox asks whether `build_saas_lifecycle_queue_event` and
`_canonical_lifecycle_payload_for_saas` should be retired. They already were, in
**#6607**, together with `_validate_lifecycle_payload` and
`repo_root_for_lifecycle_log`:

- `docs/changelog/CHANGELOG.md:222` records the deletion ("had no live caller").
- `docs/architecture/event-ledger-writers-and-readers.md:234` closes gate G-18 on
  it.
- `tests/architectural/test_events_tracker_public_imports.py` now guards all six
  production roots and rejects any `_`-prefixed module/name/attribute read
  through a name bound from `spec-kitty-events`, with no allowlist.

So this mission's scope is items 1 and 2 only. Nothing is deleted here.

## Evidence: the models are a superset of the dicts written today

Read from the installed package (`spec-kitty-events==11.3.0`, pinned
`>=11.3.0,<12` at `pyproject.toml:80`):

```
MissionReopenedPayload       frozen=True extra='forbid'
  mission_id: str (required) mission_slug: str (required) reason: str (required, min_length=1)
  reopened_by: str (required) reopened_at: str (required) cleared_merge: dict|None
FollowUpRecordedPayload      frozen=True extra='forbid'
  mission_id mission_slug follow_up_type: Literal['commit','pr'] commit_sha: str|None
  pr_number: int|None recorded_by: str recorded_at: str
ReviewerSelfApprovalPayload  frozen=True extra='forbid'
  mission_slug wp_id implementing_actor intended_reviewer failure_reason
  fallback_approved: bool timestamp: str
```

Field-for-field identical to the dicts the three emitters build today, in the
same order, with the same `None`-presence semantics. So the on-disk JSONL for a
valid call is unchanged; only *invalid* input starts failing.

The models are unchanged from 11.0.0 (the version the issue names) through
11.3.0 — same field sets, same constraints — so the issue's premise holds on the
actual pin.

## Evidence: red-first reproduction through the pre-existing entry point

```
emit_mission_reopened(feature_dir, mission_id=..., mission_slug=..., reason="", reopened_by="tester")
  → today returns a persisted envelope whose payload is {'reason': ''}
  → MissionReopenedPayload(reason="") raises ValidationError (min_length=1)
```

Same shape for `follow_up_type="pr"` with `pr_number=None` (the emitter's own
`ValueError` fires first — so the model's rejected case must be a field the
model, not the emitter, rejects, e.g. an empty `recorded_by`), and for
`emit_reviewer_self_approval(..., failure_reason="")`.

## Decisions

- **D1 — Build the payload through the model in the emitter, then
  `model_dump(mode="json", exclude_none=False)`.** Exactly the pattern
  `emit_wp_created_local` and `emit_artifact_phase_local` already use, so there
  is one construction idiom in the file, not a second.
- **D2 — Let `pydantic.ValidationError` propagate.** The file's other model-built
  emitters already raise it for bad input, and the write happens *after*
  construction, so a rejected emit appends nothing. Wrapping it would invent a
  second failure surface for the same class of bug. `ValidationError` subclasses
  `ValueError`, so existing `except ValueError` callers keep working.
- **D3 — No `schema_version` / envelope change.** `_build_envelope` is untouched;
  only the `payload` mapping's construction changes.
- **D4 — Keep the emitters' own cross-field guards** (`follow_up_type` in
  `{commit, pr}` and its required reference, the `#1926` completion guard) ahead
  of model construction, so the existing named errors and messages keep firing
  first for those cases.
- **D5 — Pin the two contract facts the issue calls out in tests**: (a)
  `reason` must be a non-empty string, so `None`/`""` is rejected; (b) each
  emitter's dumped payload validates against a freshly constructed model, i.e.
  the emitter output *is* the model's output.

## Open questions

- None blocking. CLI rendering of a `ValidationError` (a raw traceback for
  `spec-kitty mission reopen --reason ""`) is left as-is on purpose: the other
  model-built emitters have the same behaviour and changing CLI error rendering
  is a separate, user-visible decision. Noted here so review can weigh it.
