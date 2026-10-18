---
affected_files: []
cycle_number: 1
mission_slug: migration-ledger-01M55SFA
reproduction_command: spec-kitty agent tasks move-task WP04 --to approved --mission migration-ledger-01M55SFA --agent reviewer-renata
reviewed_at: '2026-10-18T06:04:28Z'
reviewer_agent: reviewer-renata
wp_id: WP04
---

Approved by reviewer-renata: approval:WP04

# WP04 Review — Cycle 1 (reviewer-renata)

**Verdict: APPROVE** — owned surface only (cross-cutting test collateral deferred to the consolidated-branch fold per operator ruling).

Scope: WP04's own 4 commits on WP01+WP02
(`448b7ff2ff`, `074a4c7bc7`, `a53fda3846`, `cc42c51f32`); range
`f6a2f1bb7c..HEAD`. Owned production surface = `metadata.py` + 4 readers.

## PART 1 — cutover source

1. **F2 (block dropped from `_model_owned_mapping`) — PASS.** The `migrations:{applied:[...]}` entry is removed from the owned mapping; `save()` no longer composes an applied block.
2. **R4 strip placement + gate — PASS.** `save()` adds `if _ledger_adopted(kittify_dir): merged.pop("migrations", None)`. Gate is load-bearing: `normalize_and_save_legacy_ids` (runner.py:250) runs BEFORE the backfill creates the ledger, so `_ledger_adopted` is False there and the block is preserved for the backfill's one read. Verified via `test_migrations_block_gone_and_stays_gone_across_save` (preserved pre-adoption; stripped post-adoption; stays gone on re-save). Lazy `from .ledger import ...` inside `_ledger_adopted` is a genuine mitigation — `ledger.py:42` imports `_LEGACY_MIGRATION_ID_MAP` from `metadata` at load, so a top-level import would be circular. Block gone AND stays gone (C-001): confirmed.
3. **F3 (record/has/applied retired as authority) — PASS.** Readable-only for the backfill's single read; runner's skip gate is `migration_settled` (runner.py:364, 573), never `has_migration`. No runner treats metadata as skip authority.
4. **F3a–d repoints — PASS.**
   - F3a `m_4_0_0rc6._is_first_application`: real call site → `not migration_settled(MigrationLedger(project_path), migration)`. `migration_settled` is success-only (`_SETTLED_RESULT`), semantically identical to retired `has_migration`; `migration is None` guard documented.
   - F3b/F3c (`decisions_event_log`, `meta_traces`): module-docstring-only; accurately describe the runner's real `migration_settled` short-circuit (no live call site in these files to repoint). Accurate, not a hollow change.
   - F3d `m_3_1_1._normalize_metadata`: real call site repointed off `metadata.applied_migrations` to reading `MigrationLedger(kittify.parent).read_all()`; justified because the ledger self-normalizes on read (`_normalize_records` applies `_LEGACY_MIGRATION_ID_MAP`, ledger.py:181) and `save()` no longer persists the list. Call site arity updated consistently (5→2 args); no orphaned param.
5. **SEAM HELD — PASS.** `git log --oneline f6a2f1bb7c..HEAD` over `runner.py`, `base.py`, `registry.py`, `ledger.py`, and the WP01 backfill = **0 commits each**. F2 alone makes WP02's transitional dual-write a no-op at `save()`.
6. **No version-floor seed — PASS.** Production diff = `metadata.py` + 4 readers only. Backfill `m_4_0_0rc8` is **byte-identical** to base (empty diff). `test_metadata_only_backfill_adds_no_version_floor_records` asserts `tracked_ids == {_PRIOR_ID}`.
7. **`test_backfill_ledger.py` (7 tests) — PASS.** Red-first genuine (F2/R4 assertions fail on base where `save()` still writes the block). Non-vacuous: drives real `ProjectMetadata.save`, `BackfillMigrationLedgerMigration().apply`, `migration_settled`. Proves no-dual-write, block-gone-and-stays-gone, gate-preserves-pre-adoption, prior-not-re-run, version-stamp survival, re-run no-op.

## PART 2 — repaired owned fixtures

8. **Green-wash check — PASS.** Spot-checked `test_auto_discovery` (manifest-order), `test_runner_status_classification` (ledger-seeded skip), `test_charter_pack_cutover_paths` (seeded-settled), `test_upgrade_outcome_rendering` (seed-all-settled). Repairs repoint seeds/assertions to the ledger/manifest authority; nothing weakened, skipped, or xfail'd to pass.

## WP-level anti-pattern checklist
1 Dead code PASS · 2 Synthetic-fixture PASS · 3 Silent return PASS · 4 FR coverage PASS (FR-012/013, NFR-003, C-001; SC-003 tracked) · 5 Frozen surface PASS · 6 Locked decision PASS · 7 Shared-file ownership PASS (sequential lane merge, not parallel conflict) · 8 Production fragility PASS.

## Deferred collateral — genuinely cross-cutting/env (NOT concealed WP04 defects)
WP04's owned diff touches **none** of: `_legacy_upgrade_fixture.py` (commit_outcomes_5443), the 4 preview harness files, the ~16 F2/F3 collateral files (incl. WP01's `test_backfill_migration.py`), or any conftest/shared helper. The reds are downstream of the REQUIRED F2 source cutover (correct behavior) and the stale-install preview SETUP failures — deferred to the fold per operator ruling.

## Fork-commit ownership integrity (`git diff --name-only`, 4 commits)
All 4 commits touch ONLY owned source (5 files: `metadata.py` + 4 readers) + owned tests + the new `test_backfill_ledger.py`. No `runner.py`/`base.py`/`registry.py`/`ledger.py`/backfill/conftest/shared-helper. PASS.

## Quality gates (owned source: metadata.py + 4 readers)
- `ruff check` — All checks passed.
- `ruff format --check --force-exclude` — 4 files already formatted (metadata.py clean under the ratchet).
- `mypy` — clean. The 3 single-file errors were import-resolution artifacts (identical "cannot subclass BaseMigration (has type Any)" reproduces on an UNTOUCHED migration; `metadata.py:385 no-any-return` vanishes to `Success: no issues found` once `.ledger` resolves — the relpaths are `str` literals, so `_ledger_adopted` genuinely returns `bool`). Zero new mypy issues.

## Independent isolation pass counts (against LANE source, PYTHONPATH=lane/src)
- `test_backfill_ledger.py`: 7 passed
- `test_auto_discovery.py`: 14 passed, 1 skipped
- `test_runner_status_classification.py`: 17 passed
- `test_charter_pack_cutover_paths.py`: 45 passed
- `test_upgrade_outcome_rendering.py`: 47 passed

No blockers on the owned surface.
