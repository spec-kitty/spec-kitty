# Data model: Event write hygiene

No data shape changes. Every surviving writer writes the same row bytes (`store.serialize_event_line`).

- **Status event log** (`kitty-specs/<mission>/status.events.jsonl`): written only through `status/store.py`'s atomic primitives. It is reached from `emit.py` (flat shell) and from `coordination/status_service.append_event_stream_log` (the `BookkeepingTransaction` funnel), plus the census families listed in `status/_unsafe.ALLOWED_CALLERS`.
- **Invocation index** (`kitty-ops/ops-index.jsonl`): a derived performance index, not an event log. It is written only by `invocation/writer.InvocationWriter._append_to_index`.
- **Produce seam registry** (`status/adapters.py`): three handler lists (status, lifecycle, resolved-binding). All are empty in open-core. Invariants:
  - registration is idempotent by qualified name;
  - every `fire_*` is non-raising and bounded by `SPEC_KITTY_STATUS_FANOUT_TIMEOUT` (default 10 s; a non-positive value runs the handler inline);
  - an empty registry is a no-op.
