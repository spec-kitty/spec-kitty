# Approach — wp-snapshot-backfill

- 2026-10-03: repair the event log rather than the reducer (ADR 2026-06-07-3). A pure planner builds deterministic seeds; the write reuses the existing migration writer so no new event-log writer appears.
- 2026-10-03: drain this repository's corpus with an evidence manifest and hold it with a set-based corpus parity gate beside the dogfood-corpus test.
- 2026-10-03 (WP01): the planner reads the gap with the read-only `materialize_snapshot` (never `materialize`) and WP ids with `read_authored_wp_frontmatter`, so a plan has no write side effects and costs one log reduction per Mission, not one per WP file. The single writer, `apply_wp_status_backfill`, sits in `backfill_runtime_state.py` beside the runtime seeder and shares its extracted `_mission_dirs` containment walk.
