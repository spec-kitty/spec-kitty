# Design decisions

See research.md R-03 (D-01..D-09). Operator rulings: decisions/DM-01M7X6R1QSXNTY0X64GQWWTZVZ.md.
- 2026-11-20 (WP01): `spec_kitty_events.diary.reduce_parsed` folds every annotation AFTER every transition. A `release_runtime_claim` annotation therefore also blanks the `agent` slot of a LATER claim (API or host): the claim event records its agent, but the slot reads empty. The fix belongs in `spec_kitty_events` (C-001), so it is filed as a follow-up. WP01 pins the claim event's sidecar, `implementer_of_record`, and the absence of the stale pid.
- 2026-11-20 (WP01): the `{"agent": actor}` injection in `tests/agent/test_orchestrator_commands_integration.py::_emit_planned_to_done` masks the accept gate, not the API claim. It is removed in WP02 together with the gate change (out-of-map edit, ownership leeway).
