# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-07 · claude · Guard-side exemption, not birth stamp (operator ruling): status_phase >= 1 also turns on the legacy frontmatter lane mirror (emit.py _legacy_lane_mirror_enabled), so stamping at birth would couple an unrelated write path and add a second status_phase writer.

2026-10-07 · claude · Terminal evidence: accepted_at/merged_at come from the existing resolve_terminal_evidence (migrate backfill-wp-status); the guard ADDITIONALLY counts a non-null mission_number (incl. 0) as terminal, failing closed. The two definitions therefore deliberately differ on mission_number; unifying them is a deferred operator decision (PR #5848).

2026-10-07 · claude · Legacy runtime = LegacyWPRuntime.has_frontmatter_runtime (claim, assignee, tracker_refs, completed review); has_evictable_state = that + subtasks. tasks.md subtask rows are canonical authoring, not legacy runtime.

2026-10-07 · claude · A missing or unparsable meta.json reads as an absent mission_id (single canonical _read_meta); its remedy names repairing meta.json before migrate backfill-identity. REASON_META_UNREADABLE was removed as unreachable.

2026-10-07 · claude · CutOverVerdict gained a structured exempt flag; the guard selects exempt verdicts by flag, not by matching the note text. JSON payload change is additive (new exempt key).

2026-10-07 · claude · Out of scope, unchanged: a coord-topology Mission whose event log lives only on its coordination branch already passes on a PR head via the no-evidence branch. Residual accepted at spec time: a Mission merged to main mid-flight without accept and with no legacy runtime is not caught.
