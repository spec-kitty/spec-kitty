# Design decisions

- Guard-side exemption, not birth stamp (operator ruling): `status_phase >= 1` also turns on the legacy frontmatter lane mirror (`emit.py` `_legacy_lane_mirror_enabled`), so stamping at birth would couple an unrelated write path and add a second `status_phase` writer.
- Terminal evidence = `accepted_at` / `merged_at` / non-null `mission_number` in `meta.json`, matching `migrate backfill-wp-status`. Acceptance matrix / VCS lock excluded: `accept` writes `accepted_at` in the same run.
- Legacy runtime = frontmatter-only slice of `LegacyWPRuntime` (claim, assignee, tracker_refs, completed review); subtask checkboxes excluded as canonical authoring.
- Coord-topology Missions whose log is on the coordination branch already pass via the no-evidence branch on a PR head; unchanged, out of scope, follow-up issue.
