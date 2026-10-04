# Contract: `spec-kitty migrate backfill-wp-status`

Operator-facing contract delivered by WP01 (engine) and WP02 (CLI). The user
documentation is `docs/migrations/backfill-wp-status.md`; this file pins the
contract the tests hold.

## Inputs

- `--mission <handle>`: optional; resolved mission_id → mid8 → slug (delegated to `cli.selector_resolution.resolve_mission_handle`, as the sibling `migrate` commands: ambiguous → `MISSION_AMBIGUOUS_SELECTOR` with `handle` + `candidates`, unknown → `MISSION_NOT_FOUND` with `handle`; exit 2 in human mode, exit 1 under `--json`, nothing written; an exact `kitty-specs/` directory name of a legacy Mission without `mission_id` short-circuits to itself). Absent → whole `kitty-specs/` corpus.
- `--dry-run`: report the plan; write nothing.
- `--evidence-manifest <file>`: YAML `missions: {<exact Mission dir name>: {reason: <non-empty text>}}`, validated before any write.
- `--json`: one JSON object on stdout.

## Behaviour

| Case | Events appended |
|------|-----------------|
| WP file with no lane event | `genesis → planned`, actor `migration:backfill_wp_status` |
| Same, Mission finished (`meta.json` `merged_at` > `accepted_at` > manifest entry) | plus forced `planned → done`, `force: true`, `evidence: null`, reason citing the evidence |
| WP with any lane event | none |
| Snapshot WP with no file | none (reported `snapshot_only`) |
| Mission whose status surface is a **live coordination surface** (coord-routing topology, coordination worktree materialised or branch still present, Mission not completed) | none: refused before any plan, `skip_reason` `COORD_SURFACE_LIVE`, also on `--dry-run` |

The PRIMARY-partition log is not the authority for a live-coordination Mission, so seeding it would split-brain the Mission: consolidate the Mission first and rerun once the coordination branch is gone. Only a gone coordination branch (`CoordinationBranchDeleted`) keeps the degrade to the PRIMARY-partition directory. Liveness is decided by the canonical surface authority (`coordination.surface_resolver.resolve_status_surface_with_anchor`), via `wp_status_backfill.coordination_surface_is_live`.

Event ids are deterministic; re-runs append nothing. Terminal evidence supplied on a later run is a no-op. `status.json` is regenerated only where it already exists; if that regeneration fails after a successful append, the row carries `refresh_error` (not `error`), the summary counts it in `refresh_warnings`, and the exit stays `0` (the events are durable; `spec-kitty materialize` regenerates the file). Writes go through the existing migration writer (`migration/backfill_runtime_state.py`, same lock and atomic verified append).

## Output

- Exit `0`: every visited Mission repaired, needed nothing, or was refused as `COORD_SURFACE_LIVE` (counted in `coord_surface_live_missions`, not in `skipped`, never an error). Exit `1`: any per-Mission error, invalid manifest, or (`--json`) unknown/ambiguous handle; exit `2`: unknown/ambiguous handle in human mode.
- JSON keys: `dry_run`, `result`, `mission`, `summary{scanned, missions_seeded, missions_would_seed, events_seeded, events_would_seed, finished_missions, snapshot_only_missions, malformed_missions, coord_surface_live_missions, refresh_warnings, skipped, errors}`, `manifest{path, entries, unused[{mission, reason}]}`, `missions[{slug, seeded, would_seed, files_only, snapshot_only, malformed, terminal_reason, status_json_refreshed, refresh_error, skip_reason, error}]`. Pre-write failure: `{success: false, error_code, error}`.

## Invariant held by the corpus gate

For every committed Mission, the WP-file id set is contained in the reduced snapshot's WP keys; extra snapshot keys are allowed only through a reasoned, exact, PERMANENT carve-out (the WP file was never committed; not drainable debt) (`tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py`).
