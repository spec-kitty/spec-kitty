# Discovery: Retry a residue-safe successor when its predecessor did not settle

Mission: `residue-successor-retry-on-unsettled-predecessor-01M67J1B` (issue #6688).

## Reproduction (current `main`, branch `issue-6688-residue-successor-retry` at `512567eee7`)

```bash
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py -k c006 -q --runxfail
```

Both parameters fail on the pinned test's own first assertion:

```text
assert NEW_311 in _selected(project, "3.2.0", "3.2.0")
E   AssertionError: ... '3.1.1_residue_safe_normalize_status_json' in
  {'0.13.1_exclude_worktrees', '3.1.1_event_log_merge_driver',
   '3.1.1_normalize_status_json', '4.0.0rc8_backfill_migration_ledger'}
```

The selected set holds the superseded predecessor and the adoption backfill, and not
the successor — so nothing repairs the dirty Mission. Without `--runxfail` the strict
`xfail` passes, which is the recorded C-006 residual.

## How the record is produced (code traced)

1. `MigrationRegistry.get_applicable(from_v, to_v, project_path)` is ledger-diff:
   `applied = migration_settled(ledger, m) or m.migration_id in pending_adoption_ids(...)`,
   then `or m.reselect_when_recorded(path)` (`src/specify_cli/upgrade/registry.py:170-186`).
2. On a pre-ledger project the tracked ledger is empty, so the only settlement evidence is
   the **pending adoption projection**: `4.0.0rc8_backfill_migration_ledger.adoption_settled_ids()`
   = the ids whose planned record result is `success`.
3. `BackfillMigrationLedgerMigration._plan()` returns (a) one record per
   `metadata.yaml` `applied_migrations` entry, **result preserved** (`failed`/`skipped` stay),
   and (b) `_baseline_items()` — a `success` for every registered migration whose
   `target_version` is below `min(recorded_version, 4.0.0rc8)` with no record.
4. The successor's `target_version` equals its predecessor's (`0.9.0`, `0.9.1`, `2.0.6`,
   `3.1.1`), all below a 3.2.0 stamp, so the baseline stamps the **successor** `success`
   while the predecessor keeps its `failed`/`skipped` record. `success` settles
   (`ledger.SETTLED_RESULT`), so the successor is not selected.
5. Even if selection were corrected, the runner's skip gate
   (`runner._apply_migration`: `if migration_settled(ledger, m) and not m.reselect_when_recorded(path)`)
   reads the record the backfill just wrote in the same pass (the backfill is first in the
   manifest), so the successor would be skipped at apply time too.

Both consumers already share one seam: `BaseMigration.reselect_when_recorded(project_path)`
is consulted by ledger-diff selection *and* by the runner's skip gate. `detect()` is, by
design (C-003), only the pre-apply idempotency guard, and every successor's `detect()` is
state-based (a residue-aware walk of `kitty-specs/`), returning False on a clean tree.

## Decisions

- **D1 — derive the successor's settlement from the predecessor's outcome (issue route 2).**
  A successor is settled only when its predecessor's recorded outcome proves the repair ran:
  `success` in the predecessor's authoritative ledger partition, or a pending adoption that
  will record it `success`. Added as `BaseMigration.predecessor_id` (declared by the four
  successors) and one registry predicate; `reselect_when_recorded` gains the same
  qualification so the apply-time gate cannot disagree with selection.
  Rationale: it is the only route that leaves the frozen backfill untouched (DIRECTIVE_044),
  keeps the manifest and `target_version` semantics intact, and needs no ledger schema change.
- **D2 — `detect()` stays the idempotency guard; no record is reinterpreted as a replay.**
  Re-evaluating a successor whose repair is done is a no-op by construction: `detect()`
  returns False and the runner records nothing new (`_record_ledger_result` is idempotent on
  `(id, result)`). `apply()` never runs on a repaired tree.
- **D3 — `predecessor_id` is declared, not inferred from the record note.** The
  `superseded_by` note (#6629) says "the shipped step never ran", which is not the same as
  "the repair did not happen"; inferring from it would make the rule depend on which process
  last appended the predecessor's no-op record.
- **D4 — unknown predecessor id keeps the old settlement.** If `MigrationRegistry.get_by_id`
  cannot resolve the declared predecessor, the recorded `success` still settles the
  successor. No invented replay for an id the codebase cannot evaluate.

## Rejected routes

- **Route 1 — mark adoption-baseline records with provenance.** Edits the frozen backfill
  (`m_4_0_0rc8_backfill_migration_ledger.py`), so it needs a supersession of the adoption
  migration plus a new ledger field and a read-compat story. Larger than the defect, and it
  changes what every project's ledger means.
- **Route 3 — move each successor's `target_version` above the adoption ceiling.** Changes
  manifest semantics (`target_version` is a declared slot and the tie annotation) and would
  silently drop the repair from every `upgrade --target` between the successor's version and
  rc8.

## Open questions

- None blocking. The `migrate ledger` read surface keeps reporting `applied` from the record
  itself; it is an audit surface (D2 in ADR `2026-10-17-1`), not the selection authority, so
  it is deliberately unchanged. The pre-existing "stale pending listing" residual (an inert
  `skipped` successor is re-listed) is unchanged and remains in the ADR.
