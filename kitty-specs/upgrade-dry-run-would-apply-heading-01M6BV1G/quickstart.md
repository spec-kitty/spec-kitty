# Quickstart — see the fix for #6234

Mission: `upgrade-dry-run-would-apply-heading-01M6BV1G`

## What to look at

The dry-run migration list in `spec-kitty upgrade --dry-run`'s human output.

**Before** (on `main` @ `287a226cfe`):

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│ DRY RUN - No changes were made                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
Migrations applied:
  ✓ 3.2.0a4_fake_migration
Migrations skipped (already applied or not needed):
  ○ 3.1.0_old_migration

Dry run complete — no changes applied. (1.0.0a1 -> 3.2.0a4 previewed)
```

**After**:

```text
╭──────────────────────────────────────────────────────────────────────────────╮
│ DRY RUN - No changes were made                                               │
╰──────────────────────────────────────────────────────────────────────────────╯
Migrations that would be applied:
  → 3.2.0a4_fake_migration
Migrations skipped (already applied or not needed):
  ○ 3.1.0_old_migration

Dry run complete — no changes applied. (1.0.0a1 -> 3.2.0a4 previewed)
```

A real run prints `Migrations applied:` with `✓`, exactly as before.

## Reproduce it in one command

The two goldens in `tests/upgrade/test_upgrade_outcome_rendering.py` capture the full text of
both modes through the real `upgrade` command, on a real git-backed fixture project:

```bash
uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py \
  -k "golden_applied" -q
```

Before the fix the dry-run golden passes while showing the contradiction; after it, the golden
holds the corrected text and `_GOLDEN_APPLIED` (the real run) is untouched.

## Prove the preview still writes nothing

```bash
uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -q
```

The module's dry-run rows assert the tree digest is identical before and after the run, so the
wording fix cannot be bought with a write.

## Where the change lives

- `src/specify_cli/cli/commands/upgrade.py` → `_display_upgrade_results` (heading and marker
  chosen once, from `result.dry_run`)
- `tests/upgrade/test_upgrade_outcome_rendering.py` → `_GOLDEN_APPLIED_DRY_RUN`
- `tests/upgrade/test_dry_run_sequenced_verdict_cli.py` → the `--dry-run` heading assertion
- `docs/guides/how-to/installation/upgrade-project.md` → one sentence describing the preview's
  list
