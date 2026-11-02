# Contracts

This mission introduces no external contract. It changes one acceptance test module
(`tests/cli/test_migrate_group_flags_4964.py`) and no production surface: no API, event schema,
CLI flag, or wire format is added or altered.

The behaviour it relies on is owned elsewhere and is only *read* here:

- `specify_cli.core.paths.git_ceiling_dirs` / `resolve_canonical_root` — the git discovery ceiling
  contract (#7022, `tests/_support/git_ceiling.py`).
- `specify_cli.migration.runtime_state_cutover._flip_phase` — the placement fail-close (FR-001) that
  this module's fixture made decide against `<tempdir>/kitty-specs/<slug>` instead of the test project.
