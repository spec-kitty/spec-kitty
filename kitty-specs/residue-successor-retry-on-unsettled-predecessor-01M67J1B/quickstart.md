# Quickstart: retry a residue-safe successor when its predecessor did not settle (#6688)

Commands are run from the repository root. This is a developer/verification guide, not an operator manual.

## Reproduce the defect (red, before the fix)

The pinned case is a strict `xfail` on `main`; `--runxfail` shows it failing on its own assertion.

```bash
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py \
  -k c006 -q --runxfail
```

Expected before the fix:

```text
assert NEW_311 in _selected(project, "3.2.0", "3.2.0")
E   AssertionError: '3.1.1_residue_safe_normalize_status_json' in
  {'0.13.1_exclude_worktrees', '3.1.1_event_log_merge_driver',
   '3.1.1_normalize_status_json', '4.0.0rc8_backfill_migration_ledger'}
```

## Verify the fix

```bash
# the pinned C-006 case, now a plain passing test
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py -k c006 -q

# the whole successor suite (retry, inertness, dry-run parity, residue safety)
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py \
  tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py -q

# ledger, registry and runner surfaces that share the predicate
uv run pytest tests/specify_cli/upgrade/test_migrate_ledger_cmd.py \
  tests/specify_cli/upgrade/test_registry_runs_first.py \
  tests/specify_cli/upgrade/test_upgrade_keyless_project_gets_ledger.py -q
```

## What the rule does, in one scenario

A project stamped `3.2.0` whose `.kittify/metadata.yaml` records
`3.1.1_normalize_status_json: failed` and whose `kitty-specs/001-legacy/status.json` still carries a
wall-clock `materialized_at`:

1. first adoption writes `failed` for the predecessor and a baseline `success` for the successor id;
2. because the predecessor's outcome does not prove the repair ran, the successor is still selected and the
   runner does not skip it;
3. `detect()` finds the stale `status.json`, `apply()` normalises it;
4. a second `spec-kitty upgrade` re-evaluates the successor, `detect()` returns False, and nothing changes.

## Invariants this mission must not break

```bash
# no shipped migration module is edited (DIRECTIVE_044)
git diff --diff-filter=MDR origin/main -- 'src/specify_cli/upgrade/migrations/m_*.py'

# the four successors keep their slot and target_version
uv run pytest tests/architectural/test_migration_order_manifest.py \
  tests/architectural/test_migration_chain_integrity.py -q
```
