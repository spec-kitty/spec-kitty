# Tooling friction — wp-snapshot-backfill

Tooling touched: `spec-kitty migrate`, status event log writer (`migration/backfill_runtime_state.py`), archive byte-freeze gate, `agent status materialize`.

- 2026-10-03: a checkout whose upstream remote is not literally named `upstream` makes the skill's `git fetch upstream` fail silently ("repository does not exist"); name the remote the skill expects, or fetch `origin` explicitly.
- 2026-10-03: `migrate backfill-runtime-state --dry-run` takes ~33 s over the corpus; too slow for an interactive loop.
- 2026-10-03: the #5579 ratchet lives in unmerged stacked draft PR #5581, so the issue's exit condition is not observable on `main`.
- 2026-10-03: `materialize()` writes `status.json` as a side effect, so a read-only corpus audit script dirtied ~80 other Missions; the first `finalize-tasks` then failed to stage and a retry rolled this Mission's event log back. Read-only audits need a non-writing reducer entry point.
- 2026-10-03 (WP01): the first pytest run in a fresh worktree builds a throwaway test venv under `.pytest_cache/` (pip install of the whole dependency set, ~45 s); later runs reuse it. Also `ruff check` with an unquoted `$F` string in zsh fails with "No such file" — pass the file list as an array.

2026-10-03 · implementer-ivan · 2026-10-03 (WP02): test_no_dead_symbols treats an __all__ name as live only with a caller OUTSIDE its module; the intra-module rescue applies to non-__all__ names only, so the per-mission engine apply_wp_status_backfill (called solely by the repo walk) had to leave __all__ — a one-line edit to WP01's owned backfill_runtime_state.py, which the scope guard flags (ACTIVE_WP_SCOPE_VIOLATION). Also: resolve_mission_handle sys.exit(2)s on an unknown handle in human mode while the WP prompt requires exit 1, and the identity resolver skips missions without a mission_id, so the CLI resolves via resolve_mission + an exact-slug legacy fallback.

- 2026-10-04 (landing folds): the WP02 note above is superseded. `--mission` now delegates to `resolve_mission_handle` (exit 2 in human mode, 1 under `--json`, like the sibling `migrate` commands); only the exact-directory-name short-circuit for a legacy Mission without a `mission_id` stays local, because the identity index cannot see it.
