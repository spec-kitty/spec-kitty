# Decision Moment `01M5HS66B8SZXZG87DZVT5PC7B`

- **Mission:** `event-write-hygiene-01M5HS55`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.strict-validation`
- **Input key:** `strict_validation_approach`
- **Status:** `resolved`
- **Created:** `2026-10-22T12:25:47.112393+00:00`
- **Resolved:** `2026-10-22T12:25:50.235199+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Without the private _EVENT_TYPE_TO_MODEL, how does lifecycle_events decide strict validation?

## Options

- Public validate_event
- Local explicit type set
- Delete the dead builder too

## Final answer

Delete the dead builder too: remove build_saas_lifecycle_queue_event, _canonical_lifecycle_payload_for_saas and _validate_lifecycle_payload (no src caller).

## Rationale

_(none)_

## Change log

- `2026-10-22T12:25:47.112393+00:00` — opened
- `2026-10-22T12:25:50.235199+00:00` — resolved (final_answer="Delete the dead builder too: remove build_saas_lifecycle_queue_event, _canonical_lifecycle_payload_for_saas and _validate_lifecycle_payload (no src caller).")
