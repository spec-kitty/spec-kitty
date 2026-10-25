---
affected_files: []
cycle_number: 1
mission_slug: residue-safe-migration-sweep-01M5SS0F
reproduction_command:
reviewed_at: '2026-10-25T18:19:19Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (reviewer-renata, cycle 1)

Verified as correct (no change needed): `_settled_in_view` is a pure extraction, so `get_applicable` behaves byte-for-byte as before. Passing `MigrationRegistry.get_all()` to `_pending_adoption_ids` matches what `get_applicable` passes, because that function reads only `ledger_adoption` migrations, which are never target-capped. The selection view stays stable mid-run: the backfill writes `success` records for the ids it settles, and a superseded substitute records only `skipped`. Dry-run and live therefore agree, as FR-007 requires. Nothing is registered, `_residue_successor` is never auto-discovered (checked after `MigrationRegistry.clear()` and re-discovery: 131 migrations, module not loaded), the `base` import is lazy, and ruff, C901<=15, format and mypy --strict are clean.

## Required

**Issue 1: the error branch of `_probe_tracked` is untested.**
`src/specify_cli/upgrade/migrations/_residue_successor.py:31-35` is new code with no test. Coverage of the module is 87%, and lines 32-35 are missed. CLAUDE.md says "every new branch/helper needs tests in the same PR", and diff-cover requires 90%. Both behaviours carry policy:
- a non-timeout `GitCommandError` switches to file-presence mode;
- a timeout re-raises.

Add two tests to `tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py`. In each, monkeypatch `specify_cli.upgrade.migrations._residue_successor.tracked_mission_paths` to raise `GitCommandError(argv=("ls-files",), cwd=p, returncode=128, stderr="corrupt index", timed_out=...)`:
- (a) with `timed_out=False`, inside the tracked `git_repo` fixture, a tasks-only folder (untracked `tasks/WP01.md`) lands in `missions`, not `residue`. This proves the fallback actually reaches `is_kitty_specs_residue` as `tracked=None`, and is the opposite of the existing tracked-mode verdict;
- (b) with `timed_out=True`, `partition_kitty_specs` raises `GitCommandError`.

## Advisory (not blocking, please consider)

2. **WP03 consumer shape.** WP03 calls `partition_kitty_specs(<wt>/kitty-specs, <wt>)` for `.worktrees/*/kitty-specs`. No test passes a worktree checkout root today. A short case that partitions a `.worktrees/wt1/kitty-specs` tree with `checkout_root=<wt1>` and feeds the residue into `residue_warnings(residue, project)` would pin the path WP03 relies on.
3. **Duplicated probe policy.** The policy "timeout re-raises, any other `GitCommandError` gives file-presence mode" now has two copies: WP01's inline block in `is_kitty_specs_residue` (`mission_resolver.py`) and `_probe_tracked`. WP02 does not own `mission_resolver.py`, so this is acceptable here. Note it for a follow-up so that one probe helper owns that policy.
4. **Stale task file in the lane.** `kitty-specs/.../tasks/WP02-*.md` and `tasks/WP03-*.md` in this lane worktree are the pre-re-cut versions (WP02 with T006-T011 successors; WP03 refers to a non-existent `_residue_successor.non_residue_dirs`). The authoritative re-cut versions live in the primary checkout. No action is needed in code; flagging it so WP03 reads the re-cut prompt.
