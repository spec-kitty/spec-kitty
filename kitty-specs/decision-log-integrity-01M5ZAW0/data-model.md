# Data Model: Decision log integrity

No schema change. Rules this mission enforces over existing shapes:

- **Opening record** (`DecisionPointOpened` row in `status.events.jsonl`): the CLI appends at most
  one per `decision_point_id` (invariant, FR-001/FR-002).
- **Fold of one decision's rows** (`index_fold.fold_events`):
  - one or more opening rows whose payloads are equal after removing `recorded_at` fold from the
    earliest by `(payload.recorded_at, event_id)` (FR-003);
  - opening rows whose payloads differ in any other field raise `FoldError` (unchanged);
  - terminal rows: unchanged; the reopen pair comes from
    `spec_kitty_events.decisionpoint.DECISION_POINT_TERMINAL_REOPEN` (FR-004).
- **Lock order**: `decisions/index.json.lock` → Mission status lock (C-001).
