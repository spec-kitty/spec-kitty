# Research: Cutover guard exempts pre-accept Missions

## R1 — Fix direction
- **Decision**: guard-side exemption in the shared cut-over predicate.
- **Rationale**: the stamp is deferred to accept on purpose (#2917, FR-004 of `runtime-state-birth-cutover-all-paths-01KYH654`), and `status_phase >= 1` also enables the frontmatter lane mirror (`src/specify_cli/status/emit.py` `_legacy_lane_mirror_enabled`).
- **Alternatives**: birth stamp (rejected: second writer, mirror coupling); message-only stopgap (rejected: leaves the P0 red).

## R2 — What counts as legacy runtime
- **Decision**: a new `LegacyWPRuntime.has_frontmatter_runtime()` — claim state, `assignee`, `tracker_refs`, completed review override.
- **Rationale**: `has_evictable_state()` includes `tasks.md` subtask checkboxes, present in every native Mission; `move-task` is event-only since the IC-04 flip, and the WP template ships empty claim fields that the reader maps to `None`.
- **Alternatives**: reuse `has_evictable_state()` (rejected: exemption never fires); a separate reader (rejected: C-003).

## R3 — Terminal evidence
- **Decision**: non-empty `accepted_at` / `merged_at`, non-null `mission_number`.
- **Rationale**: same fields as `migrate backfill-wp-status`; `accept` writes `accepted_at` (`mission_metadata.py` `record_acceptance`) and stamps best-effort, so "accepted, not stamped" is reachable and must stay red.

## R4 — Second consumer
- **Decision**: `eligible_runtime_missions` excludes exempt Missions.
- **Rationale**: `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py` reaches the invariant through `assert_birth_invariant_holds`, which checks `status_phase` directly and never calls `is_cut_over`.

## R5 — Corpus baseline
- 2026-10-06 on this branch: 576 PASS, 5 FAIL (absent `mission_id`), 0 hitting the phase branch. NFR-001 is therefore proven by a synthetic matrix, with the corpus count as a no-drift check.
