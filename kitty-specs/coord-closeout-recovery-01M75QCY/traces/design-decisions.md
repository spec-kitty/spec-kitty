# Design decisions

- **DD-1 (status_phase).** `status_phase: "1"` in the acceptance record is the accept-time birth cutover stamp (`stamp_accept_cutover`, #2917), deliberate. Kept; documented in the spec and PR, not dropped.
- **DD-2 (residue context).** Fix `ResidueContext.for_mission` (read the stored topology where the placement seam puts `PRIMARY_METADATA`) instead of special-casing rollback: one authority, and every destructive-guard caller had the same blind spot.
- **DD-3 (advance intent).** Route `safe_commit` through its existing expected-parent mode while a consolidate rollback span reports advance intents, instead of teaching the rollback to recognise its commits by message: an intent is a record; a message is forgeable.
- **DD-4 (rematerialization).** Keep `--abort`'s teardown (ruling); the next run reads the Mission's identity from the branch that holds it and calls `materialize_coord_surface_for_write` with the explicit `coordination_branch` + `mid8` override.
