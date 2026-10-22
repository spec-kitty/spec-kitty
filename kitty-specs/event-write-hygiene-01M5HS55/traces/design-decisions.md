# Design decisions

- **[2026-10-22][specify] Delete the dead hosted builder (operator ruling).** The alternatives were the public `validate_event` with its unknown-type `ValueError`, or a local explicit type set. Deleting removes the private import and the latent 11.1.0 `actor_id` strictness break together.
- **[2026-10-22][specify] No compatibility aliases (operator ruling).** `spec-kitty/event-router` is frozen and considered dead, so no old names are kept for it. The timeout env var `SPEC_KITTY_SAAS_FANOUT_TIMEOUT` goes too.
- **[2026-10-22][post-spec squad] Extend existing gates; add no new scanners.**
  - The door bans ride on `test_status_unsafe_allowlist.STORE_APPEND_PRIMITIVES` / `COORD_WRAPPER_DOORS`, the `test_store_writes_are_found` pin and `test_no_dead_symbols`.
  - The private-import ban extends `test_events_tracker_public_imports.py`, the real owner. G-18's pointer to `test_shared_package_boundary.py` was wrong.
  - Reason: single canonical authority.
- **[2026-10-22][post-spec squad] Private-import gate covers `src/` only, with no allowlist.** Four test files deliberately read `diary` privates to stay in step with the library. A test allowlist would be priced debt (charter burn-down policy). An upstream request for public equivalents is proposed instead.
- **[2026-10-22][post-spec squad] The rename covers the seam's full residue, not only `adapters.py`.** That includes `emit._saas_fan_out*`, the seam log labels, `fanout_lifecycle_event_hosted` and the `conftest_saas_sink` plugin, with path-keyed ledgers updated. Renaming only `adapters.py` would satisfy SC-003 on paper only.
- **[2026-10-22][post-spec squad] `repo_root_for_lifecycle_log` goes with the hosted builder.** It existed only for the removed sync handler.
- **[2026-10-22][plan] Census folds (`research-census.md`).**
  - 190 files are codemodded, including the identity spy at `refinalize_frozen_lanes_support.py:311`, which is deleted, and 45 function-local imports.
  - The `conftest_saas_sink` patch becomes fail-loud: an unconditional `setattr` that raises when the target is missing, so the `call_count == 0` assertions cannot pass vacuously.
  - The `append_to_index` "index entry without op file" seed becomes a raw fixture line written by the test.
  - `emit._saas_fan_out*` is in scope (operator: no stale names).
  - `status/design.py:79`'s same-inode claim gets corrected.
  - The `coverage_breadth_baseline.json` node IDs follow the test rename.
