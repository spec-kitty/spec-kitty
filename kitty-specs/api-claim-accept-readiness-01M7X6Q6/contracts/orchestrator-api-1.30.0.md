# orchestrator-api contract 1.30.0 (minor)

No field and no `error_code` is removed or renamed.

- `start-implementation` and `transition --to claimed`: the claim event's `policy_metadata` now holds `agent` = `--actor` beside the `--policy` keys. A `--policy` key named `agent` cannot override it. The snapshot `agent` slot is filled, so the host `move-task` ownership guard applies to API-claimed WPs.
- `transition --to planned`: releases the runtime claim (`agent`, `shell_pid`, `shell_pid_created_at`) and clears the review override, as `move-task --to planned` does. `implementer_of_record` is kept.
- `accept-mission`: `incomplete_wps` now lists only WPs that are not at an acceptable ending. A WP canceled with operator provenance is no longer listed; a synthetic cancellation still is. A call that refused `MISSION_NOT_READY` for such a WP can now succeed.
- `accept-mission` / host `accept`: the "missing agent" readiness issue is raised only for a WP with no implementing claim in the event log, and never for a canceled WP without one. Its text names a command only when one is legal from the WP's lane.
