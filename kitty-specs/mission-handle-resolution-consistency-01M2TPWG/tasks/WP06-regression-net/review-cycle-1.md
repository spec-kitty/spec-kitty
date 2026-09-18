---
affected_files: []
cycle_number: 1
mission_slug: mission-handle-resolution-consistency-01M2TPWG
reproduction_command: spec-kitty agent tasks move-task WP06 --to approved --mission mission-handle-resolution-consistency-01M2TPWG
reviewed_at: '2026-09-18T20:39:08Z'
reviewer_agent: user
wp_id: WP06
---

Approved by user: Review passed (reviewer-renata, final pre-consolidation). WP06 deliverable (21d39c6d): T028 canonical 'Mission not found: <h>' asserted across research/setup-plan/check-prerequisites/merge-fresh + old defect strings ('to disambiguate','lanes.json is required') absent; T029 byte-identical kitty-specs snapshot incl. phantom-dir guard; T030 both PRESERVED envelopes proven NOT flattened (identity resolver names handle+backfill-identity+message!=canonical; reconcile 'dossier not found', canonical absent); T031 legacy no-mission_id mission staged, next==setup-plan==check-prerequisites populations agree incl. legacy, count==2. Real in-process CliRunner, no source mocking (only scoped dashboard-preflight bypass mirroring WP05 baseline). Consolidation fixes (d57ab765): (1) next_cmd _missing_handle_or_sole_slug now calls WP01 sole_mission_for_selection — behavior-preserving (1->slug, 0/>1->raise MissingHandleDiscovery(listings)) and a genuine live caller fixing the dead-symbol gate; (2) pyproject dropped 2 stale ruff-format excludes (mission_feature_resolution.py, test_wp02_no_selector_exit2.py) — both now format-clean, shrink-only, sibling test_mission_feature_resolution.py correctly retained. Ran: 21 passed (WP06 suite + WP05 discovery); arch gates test_no_dead_symbols::test_no_public_symbol_in_all_is_unimported + test_ruff_format_exclude_ratchet + test_pyproject_shape = 14 passed; ruff check + format --check clean.
