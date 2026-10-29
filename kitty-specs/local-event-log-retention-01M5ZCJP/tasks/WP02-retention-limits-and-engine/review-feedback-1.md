# WP02 review feedback, cycle 1 (reviewer-renata)

Verdict: changes requested. One blocking data-safety defect (FR-008). Everything else is good:
red→green ordering, C-001, FR-013 drift guard, fail-closed config, lock order, tests and gates
(except the accepted dead-symbol gate) are green.

## Blocking

1. **FR-008 / Mission identity: a run of an unknown Mission is pruned when its legacy slug collides.**
   `src/specify_cli/state/retention.py:377` (`_read_run_mission`):
   `return missions.by_id(state.get("mission_id")) or missions.by_slug(state.get("mission_slug"))`.
   When the run snapshot records a `mission_id` that this checkout does not have, the code silently
   falls back to the slug. A run of Mission `01OTHER…` (on another branch) whose slug is `001-done`
   is then judged by the local, completed `001-done` and DELETED. Reproduced: run dir with
   `{"mission_slug": "001-done", "mission_id": "01OTHERBRANCH"}`, 90 days old, `keep_runs=0` →
   candidate `past retention; Mission completed`, removed by `apply_retention`. That is exactly the
   "Mission on another branch is never pruned" case FR-008 protects, and the `NNN-` slug collision
   `mission_id` exists to fix ("mission_id is the only runtime identity … no silent fallback").
   **Required change:** when the snapshot carries a non-empty string `mission_id`, resolve by id
   only (unresolved → `None` → `Mission not found`); fall back to the slug only when no
   `mission_id` is recorded. (Optionally also refuse a slug match whose `meta.json` carries a
   different `mission_id`.) **Required test** in `tests/core/test_event_log_retention.py`: a run with
   `mission_id=UNKNOWN_ID, slug=DONE_SLUG`, 90 days old, `LIMITS_NO_KEEP` → kept,
   `REASON_MISSION_NOT_FOUND`, `mission is None`, and `apply_retention` leaves the directory.
   Keep `test_run_resolves_its_mission_by_slug_when_the_id_is_absent` green.

## Non-blocking (fix if cheap, else note in the PR)

2. `retention.py:633-647` `_delete_run`: index entries are dropped before `rmtree`. A failed or
   partial `rmtree` (Windows open handle, permissions, symlinked run dir) leaves the run on disk
   with no index entry while the item is reported `failed`. Consider dropping the entries only after
   the tree removal succeeded (still inside both locks), or say in the docstring why this order wins.
3. `retention.py:622-630` `_drop_index_entries`: `read_index_file` can return a non-dict (an index
   holding a JSON list); `index.items()` then raises `AttributeError`, which escapes the
   `apply_retention` loop (only `OSError`/lock errors are caught) and aborts the remaining deletions.
   Guard with `isinstance(index, dict)`.
4. Path guard `_assert_deletable` (`:588`) is lexical (`normpath`), not `resolve()`. Safety currently
   rests on `shutil.rmtree` refusing a top-level symlink and `unlink` removing only the link (both
   verified). But a symlinked run dir is still collected and, at apply, `try_run_cursor_lock` creates
   `state.json.lock` inside the symlink's target outside the repo. Suggest skipping symlinked units
   at collection (`entry.is_symlink()`), with a test.
5. Scan robustness: an `OSError` raised by `with probe:` in `_lock_is_held` (e.g. EACCES,
   `NoFollowPathError`) or by `_newest_mtime` on a file that vanishes mid-scan aborts the whole
   preview. Consider reading such an item as `lock held` / skipping it.
6. FR-011 "every tracked file": the guard is path-based only; no `git ls-files` check. The WP prompt
   accepted the cheap guard; record it as a residual for consumer projects whose `.gitignore` lacks
   the local-tier rules.

## WP03 must clear the dead-symbol gate

`tests/architectural/test_no_dead_symbols.py` is red only because these names have no `src/` caller
yet. WP03's CLI module must import each of them, or the name must leave `__all__`/become private:
- `specify_cli.core.ledger_retention`: `load_retention_limits`, `RetentionConfigError`,
  `CONFIG_SOURCE`, `DEFAULT_SOURCE`, `DEFAULT_KEEP_RUNS`, `DEFAULT_MAX_AGE_DAYS`
  (the last four are likely better dropped from `__all__` unless the CLI renders them).
- `specify_cli.state.retention`: `scan_retention`, `apply_retention`, `RetentionPlan`,
  `RetentionResult`, `RetentionItem`, `RetentionFailure`, `RetentionPolicyDriftError`,
  `UnsafeRetentionPathError`, `KIND_RUN`, `KIND_MISSION_LOG`, `KIND_CACHE`, `VERDICT_CANDIDATE`,
  `VERDICT_KEPT`, `REASON_COMPLETED`, `REASON_REBUILDABLE`, `REASON_WITHIN_KEEP_RUNS`,
  `REASON_YOUNGER_THAN_MAX_AGE`, `REASON_MISSION_OPEN`, `REASON_MISSION_NOT_FOUND`,
  `REASON_LOCK_HELD` (constants the CLI does not use should leave `__all__`; tests can still import them).
