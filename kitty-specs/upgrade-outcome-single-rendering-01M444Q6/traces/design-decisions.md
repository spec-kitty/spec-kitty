# Design decisions

- 2026-10-04 — Unresolved drift keeps a non-zero exit. Pinned by earlier missions, tests and the changelog; reversing it is an operator decision, recorded as open in the spec.
- 2026-10-04 — Four kinds, with `failed` taking precedence over `drift_unresolved`. `applied` versus `no_op` is decided by whether migrations were applied, not by whether supporting files were refreshed; this keeps today's `success` / `up_to_date` JSON vocabulary.
- 2026-10-04 — The overloaded `surface_drift_failed` boolean is replaced by `drifted_paths`, `surface_repair_failed` and `preview_incomplete`. This removes the `drift in 0 file(s)` message by construction.
- 2026-10-04 — Drift on the migrations path changes its closing line from `Upgrade failed.` to `Upgrade finished with unresolved tool-surface drift.` Migrations did apply; the old line overstated the failure.
- 2026-10-04 — JSON gains `outcome` and `failure_reasons`; no key is removed or renamed.
- 2026-10-04 — The ordering defect behind the first-run failure on old projects is not fixed here; a single outcome only reports it honestly.
- 2026-10-04 — Post-tasks review: a failed auto-commit recovery set `result.success = False` and would have been reported as `migration_failed` on a run with no migrations. It gets its own reason (`commit_recovery_failed`); same defect class, folded into WP02.
- 2026-10-04 — Text format: success kinds keep today's output exactly; non-success kinds share one format on both paths (warnings, errors, manual review, closing line last). Golden-output tests characterise the success formats before the change.
- 2026-10-04 — WP01 confirmed the legacy surface-repair branch unreachable through the real command (six cases) and removed it. `repair_stale_manifest` and `remove_unsafe_symlinks` are left without a production caller; recorded as a follow-up, not fixed here.
- 2026-10-04 — After a failed commit recovery the optional mission-state repair is not offered (kept from before; now keyed on `commit_recovery_failed`).
- 2026-10-04 — A surface-repair or preview reason that recorded no message gets its own generic line even when other messages exist; other reasons get one only when the list would otherwise be empty.
- 2026-10-04 — The mission-state gate prints its own failure text, so `warnings()` lists a repair failure only when the finalizer's isolation boundary caught it (`RepairOutcome.surface_message`), to avoid printing it twice.
