# Decision Moment `01M6EKGB7RZVKSKWBEZN5EWAXM`

- **Mission:** `op-record-model-and-coauthor-01M6EJV5`
- **Origin flow:** `plan`
- **Slot key:** `plan.record.model-field-disposition`
- **Input key:** `model_field_disposition`
- **Status:** `resolved`
- **Created:** `2026-11-02T17:04:26.872806+00:00`
- **Resolved:** `2026-11-02T17:04:33.945486+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Drop model_id from the Op started event, or replace it with a non-identifying field?

## Options

- Drop the field entirely
- Replace with an opaque non-identifying token

## Final answer

Drop the field entirely. actor already carries the harness key, the issue pre-authorises the drop, and any replacement token derived from a model id is the same identifier wearing a hat. Consequence handled explicitly: the claim cannot assert --model from the Op, so the resolved-binding model slot becomes explicit-absent (RESOLVED_MODEL_ABSENT) rather than fabricated.

## Rationale

_(none)_

## Change log

- `2026-11-02T17:04:26.872806+00:00` — opened
- `2026-11-02T17:04:33.945486+00:00` — resolved (final_answer="Drop the field entirely. actor already carries the harness key, the issue pre-authorises the drop, and any replacement token derived from a model id is the same identifier wearing a hat. Consequence handled explicitly: the claim cannot assert --model from the Op, so the resolved-binding model slot becomes explicit-absent (RESOLVED_MODEL_ABSENT) rather than fabricated.")
