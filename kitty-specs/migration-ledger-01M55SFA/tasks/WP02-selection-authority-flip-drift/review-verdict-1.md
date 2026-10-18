# WP02 Review Verdict — APPROVE

**Reviewer:** reviewer-renata · **Mission:** migration-ledger-01M55SFA · **Date:** 2026-10-18
**Range:** `kitty/mission-migration-ledger-01M55SFA..kitty/mission-migration-ledger-01M55SFA-lane-b` (4 WP02 commits on WP01)

Adversarial review of the migration SELECTION-authority flip from version-window to ledger-diff.
**Verdict: APPROVE.** No blockers. One minor, non-blocking terminology note.

## Decision-by-decision findings

- **(A) Manifest is sole ordering authority; `runs_first` front-pull deleted — VERIFIED (honest).**
  `get_all` now sorts by `order_manifest.txt` index with `Version()` as a fallback only for
  non-manifest (planted) classes. `test_real_get_all_is_manifest_order_with_backfill_leading` runs
  the REAL registry (`auto_discover_migrations`), asserts `get_all() == load_order_manifest()`,
  asserts the backfill leads at index 0, and proves it is NOT version-order (`rc8 > index-1
  version`). Non-vacuous. `_detect_fail_closed`, `_clone_local_selected_below_window`,
  `_runs_first_selected_outside_window`, `_order_runs_first` all deleted with no live caller;
  `test_the_6233_selection_machinery_is_deleted` guards their absence.

- **(B) #6233 clone-local regression net — VERIFIED (strong).** Selection authority for a
  clone-local migration is its per-clone ledger partition (`MigrationLedger.applicable_records_for`
  routes by `clone_local_effect`). `test_pulled_clone_selects_clone_local_via_empty_per_clone_ledger`
  proves an empty per-clone partition re-selects then a recorded one settles; the real `upgrade()`
  path lands the effect on disk (exclude-worktrees + merge-driver). `test_clone_local_recorded_only_
  in_tracked_partition_is_still_selected` proves partition routing (a record in the WRONG partition
  does not settle). The per-clone partition genuinely carries what the deleted #6233 code carried.

- **(C) `can_apply` refusal → skip, placed in the RUNNER — VERIFIED (sound).** `_apply_migration`
  now returns `success=True`/status `skipped` (+warning) on a `can_apply` refusal instead of
  `failed`; a genuine `apply()` failure still records `failed` and fails the run. Keeping this out of
  `get_applicable` is correct: selection stays pure ledger-diff (no FS probing of ~125 migrations,
  C-003 — detect/can_apply are idempotency guards only), and a SupersededMigration still reaches the
  runner to earn its `skipped` record (FR-008). No pre-existing main-path test asserted
  `can_apply`→failed; the worktree can_apply test was already warn-and-continue, and the concurrency
  test at `test_migration_robustness.py:244` passes via its "Upgrade lock" OR-branch.

- **(D) `migration_settled` is SUCCESS-only AND id-matched — VERIFIED.**
  `record.id == migration_id and record.result == "success"`. A `skipped` record re-evaluates and
  re-skips idempotently (`test_superseded_migration_records_skipped_once_and_never_refires`, owned);
  a `failed` record allows retry (`test_migration_robustness::test_failed_migration_can_retry` +
  `test_issue_4872_lifecycle_migration_retry` — both pass). Not over-broad, not under-matched.

- **(DEVIATION) Dual-write ledger + `metadata.record_migration` instead of literal "instead of" —
  SOUND seam discipline, not a hidden defect.** Selection reads ONLY the ledger: `migration_settled`
  → `ledger.applicable_records_for` → the JSONL partitions, never `metadata.yaml`. The retained
  metadata write is transitional (legacy readers + the WP01 adoption backfill, which seeds from
  `metadata.applied_migrations`) and becomes a no-op at WP04's `save()` cutover. Provably harmless to
  selection. A literal "instead of" now would strand metadata-assertion tests owned by neither WP —
  correct call.

- **(ESCALATION) Empty-ledger-selects-everything — REAL cross-WP sequencing finding, NOT a concealed
  WP02 defect.** Independently reproduced: on a version-only synthetic fixture (empty ledger, no
  `metadata.applied_migrations`) `get_applicable` returns all 125/125 declared migrations — the
  inherent, by-design consequence of the flip. Real projects are bridged: the WP01 backfill
  (`m_4_0_0rc8_backfill_migration_ledger`, manifest index 0) populates the ledger from
  `metadata.applied_migrations`, and the runner's skip-gate re-reads the ledger per migration, so the
  backfilled records settle the rest within the same run. Only synthetic fixtures with a `version=`
  but no applied history are over-selected — those live in WP04 (cutover) / WP05 (acceptance),
  confirmed outside WP02's owned surface. **Zero owned-file failures** (all 4 owned suites green).

## Quality gates (owned source only)
- `ruff check`: clean. `ruff format --check --force-exclude`: clean (registry.py + detector.py are
  on the pre-existing #473 format-debt ratchet and are also format-clean when checked explicitly).
- `mypy`: 3 `no-any-return` errors — all confirmed **pre-existing** on the base branch
  (`detector.py:44`, `runner.py` `_aligned_worktree_timestamp` + `_record_migration_result`-return;
  same functions, line numbers shifted by WP02 additions). No new suppressions added. Complexity fine.

## Owned test runs (independently executed)
- `test_registry_runs_first.py` + `test_clone_local_selection.py` +
  `test_clone_local_migration_idempotent.py` + `test_ledger_drift.py`: **57 passed, 0 failed** (0.65s).
- Decision-D retry evidence (non-owned, named in report): `test_failed_migration_can_retry` +
  `test_issue_4872_lifecycle_migration_retry`: 2 passed.

## Minor, non-blocking
- The backfill migration is NOT the `runs_first` ClassVar (that is `charter_pack_cutover`); it "leads"
  only by manifest index 0. The manifest comment and the test docstring ("annotated runs-first lead")
  use "runs-first" in the ordering sense, which can be confused with the `runs_first` flag. Behavior
  is correct and tested; consider rewording to "manifest-first" in a later pass. Not a change request.
