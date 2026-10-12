# Tracer: design-decisions — remove-dead-compat-repair (#6095)

- **[2026-10-12][plan] Keep `_legacy_contract_carriers` / `_matches_legacy_contract` / `_LegacyCarrier`.**
  #6095 lists them for removal, but the reference census shows they are LIVE: `_verify_expected_seed_events`
  (1966) and `_seed_row_mismatch` (1928) use them to tolerate a legitimately-shaped pre-floor
  seed during verify. Removing them would change live verify behaviour. Steer honored:
  "remove only if it becomes unreferenced."
- **[2026-10-12][plan] `_misaligned_seed_wps` IS removed.** Both its callers
  (`_plan_compatibility_repairs`, `_verify_compatibility_repairs`) are repair code; once they
  go it is unreferenced. Its dependency on the kept carriers is one-directional, so removal is clean.
- **[2026-10-12][plan] `_is_migration_actor` kept, repair branch dropped.** It folds the LIVE
  `BACKFILL_ACTOR` (used by `_wp_events`, `_stream_without_migration`, `_seeded_frontmatter_slots`);
  only `COMPATIBILITY_REPAIR_ACTOR` leaves the tuple. `_wp_events` loses its now-unused
  `include_seeds=True` branch (the only user was `_compatibility_repair_at`).
- **[2026-10-12][review] Independent review (code-review skill) surfaced 4 findings; folded 2.**
  F2 (`_SEED_RUNTIME_SLOTS` orphaned) and F4 (`require_superseded` param + `_LegacyCarrier.fully_superseded`
  field/computation dead) were dead code my own removal created — folded in (collapsed `_LegacyCarrier`
  to a plain `StatusEvent`, dropped the dead param/field and the now-unused `stream` arg). This honours
  "follow the dead-reference chain; nothing left dangling."
- **[2026-10-12][review] F1 (verify_backfill lost the builder-independent snapshot-equality backstop) —
  accepted as a reasoned scope boundary.** The removed loop lived in `_verify_compatibility_repairs`,
  emitted repair-framed mismatch text ("compatibility repair did not restore ..."), and is vacuous under
  10.4.4 (desired == actual by #6095's reduction argument). Re-adding a non-repair end-state assertion would
  change verify's live refusal set / behaviour, violating the NON-GOAL "no change to refusal text/exit code
  for a live path." The kept guards — `_verify_expected_seed_events` (seed-row presence + pre-floor
  tolerance) and `_verify_claim_slot_witnesses` (independent claim-slot parity) — remain fail-closed;
  guarding the external reducer's fold correctness is events' contract, not the backfill's. Documented in PR.
- **[2026-10-12][review] F3 (`_shift_ordering_timestamp` "after" direction now production-dead) — declined.**
  It is a live, correctness-sensitive lexical-ordering utility (not repair machinery) still used by
  `_wp_history_floor` (direction "before") and covered bidirectionally by `test_shift_ordering_timestamp_*`.
  Narrowing it to one direction would refactor a load-bearing floor helper and churn its tests for a
  cosmetic dead-branch win — against smallest-viable-diff + behaviour-preservation. Kept general; documented.
- **[2026-10-12][plan] ATDD/red-first tension flagged.** Charter C-011 wants a failing-first
  test per WP; this is a behaviour-preserving deletion, so the "contract" preserved is the
  already-green end-state/idempotency coverage plus gate greenness, not a new red test. This is
  the tidy-first carve-out (Standing Order 2 / `RECONCILE_CHANGE_SCOPE_TENSIONS`). Flagged in PR.
