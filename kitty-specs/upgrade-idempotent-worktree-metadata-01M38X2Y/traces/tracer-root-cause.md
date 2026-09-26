# Tracer: root-cause map (#4972) — post-adversarial-review, line-verified

## The single mint site (fix locus)
- `src/specify_cli/upgrade/runner.py:541` `wt_metadata.last_upgraded_at = now_utc()` — the ONE per-worktree timestamp mint. Saved at `:542`, auto-committed at `:561` (`commit_touched_checkout`). Fires whenever `worktree_metadata_dirty` is True.
- `runner.py:536` `if wt_metadata.version != target_version:` → `:537-538` sets `version=target` AND `dirty=True`. **This is the exact branch that lets the divergent stamp through** on the no-migrations (already-current) path.
- Fix here (the shared stamp), NOT in the CLI wrapper: `_upgrade_worktrees` (`runner.py:374`) has THREE callers — `:260` `upgrade_worktrees_only` (CLI no-migrations, the repro), `:159` (MigrationRunner.upgrade no-migrations sub-branch, `include_worktrees and from_version==target_version`), `:219` (migrations-pending). A CLI-only fix in `_run_no_migrations_worktree_stamp` (`upgrade.py:808`) misses `:159` and `:219`.

## Prior-art correction
- `#1838` save-gate: `runner.py:531-542` — suppresses when `version==target` (dirty stays False), does NOT when `version!=target`. Extend THIS gate.
- `#1872` suppression: `runner.py:474-486` + `_record_migration_result` (`:599-607`) — gates migration-RECORD writes only; inert on the no-migrations path. NOT the gate to reuse (spec originally mis-referenced it).
- `schema_version` stamping `runner.py:549-550` — compare-before-write (#1871), writes shared REQUIRED_SCHEMA_VERSION; NOT a divergence source.

## #2385 preservation
- Auto-commit churn-gated: `commit_touched_checkout` returns `(False, [], None)` on empty baseline delta (`autocommit.py:388-390`); baseline captured before any write (`runner.py:420`). Suppressed/aligned write → nothing to commit, self-cancels.
- MUST still stamp+commit for genuine change: worktree migration applied content (`runner.py:503-511` sets dirty=True) or synthesized metadata (`runner.py:435`). Gate the aligned write on "sole driver is the version bump".

## Entry-point coverage
- `upgrade.py:822` `if no_worktrees or current_version != target_version: return` — runs precisely when `current_version == target_version` = operator repeat run AND teammate first-run on already-upgraded main. Both funnel to `runner.py:536-541`.

## Consumers (NOT changed — prevention-only)
- `src/specify_cli/lanes/merge.py` + `lanes/stale_check.py` — lane refused stale / dependency auto-merge conflict on `.kittify/metadata.yaml`. Left as-is per operator decision.

## Other per-worktree/main writes (confirmed NOT the bug)
- `runner.py:147`, `runner.py:631`, `upgrade.py:797` — all MAIN-checkout `last_upgraded_at`, not per-worktree.
