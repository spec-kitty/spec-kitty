---
affected_files: []
cycle_number: 2
mission_slug: mission-writer-followups-01M4CYWW
reproduction_command:
reviewed_at: '2026-10-08T19:51:44Z'
reviewer_agent: claude-reviewer
wp_id: WP04
---

# WP04 review cycle 2: changes requested

Cycle-1 item 1 (the per-write ledger) is fixed in substance. Item 2 (the armed pin) is green, but only
because the reads the pin catches were rewritten so it can no longer see them. That is item 1 below.

## Blocking

1. **The armed pin is green because the reads moved to a copy of the code it checks
   (`641f3b697`, `status/mission_write.py::_main_checkout_of_worktree`).**
   Cycle 1 said: "Do not add owned-path R reads. Pass the owned checkout's own root to the lock."
   The fix keeps every one of those reads. `_primary_meta` still works out the repository root
   from the owned worktree's `.git` pointer and reads R's `meta.json`. It now does that with its own
   copy of `core.paths.get_main_repo_root`'s pointer parse, and the armed pin cannot see that copy.
   Reviewer check: put back `literal_primary_meta(root, name)` in `_primary_meta` and
   `test_armed_get_main_repo_root_pin_owned_finalize` fails again with the same 7 reads. I added
   instrumentation, and the copy fires on the same call paths:
   - `_flush_frontmatter_writes(..., repo_root=ctx.repo_root)` (`mission_finalize.py:1013`). This
     goes into `locked_update_frontmatter` > `mission_write_lock`, through both `mission_lock_key`
     and `_primary_alias`. In an owned run, `ctx.repo_root` is the owned worktree, not
     `owned.repository_root`.
   - `StatusSurfaceGuard.recording` (`finalize_status_surface.py:195`), which calls
     `mission_lock_key(status_dir, repo_root=surface_root)`.
   - `bootstrap_canonical_state` > `emit_status_transition_transactional` > `transaction.acquire` >
     `_transaction_lock_key` (`legacy_resolution.py:65`) > `transaction_lock_key`.

   This also breaks single canonical authority: there are now two parsers of the worktree `.git`
   pointer, and they already behave differently. The new one accepts relative `gitdir:` paths. Both
   assume `<x>/.git/worktrees/<n>`, so with a separate git dir named `.git` (for example
   `--separate-git-dir=/store/.git`) both return `/store`.
   Fix: pass the fact's `owned.repository_root` as the lock root at those three sites. The fact
   carries it, and a root whose `.git` is a directory takes the `own` branch. Then remove
   `_main_checkout_of_worktree`, and re-run the pin with `_primary_meta` back on
   `literal_primary_meta`. If a site cannot get at the fact, list it in the pin's
   `_RESOLVER_READ_LEDGER` with a reason. Do not hide it.

2. **FR-003 / A8: the restore brings back a file that another writer deleted, even when finalize
   never wrote it.** In `_restore_mission_write_scope`, the check
   `written is not None and now is not None and now != written.get(...)` lets `now is None` fall
   through to `_undo_one_path`. A file that existed before the run and is now gone is rewritten
   from `before` whatever the ledger says. `test_restore_puts_back_a_file_that_is_gone` pins this
   with `written={}`, that is, with a ledger that says finalize wrote nothing. A8 says the restore
   "acts only while the current bytes equal what finalize wrote". A deletion is a concurrent
   change too.
   Reviewer mutation: treat "gone" as kept whenever a ledger is present (compare against a
   sentinel rather than `None`). Only that one test goes red. `test_finalize_atomicity.py`,
   `test_finalize_clobber_e2e.py`, `test_issue_5328_refresh_fail_closed.py`,
   `test_finalize_tasks_commit_surface.py` and the rest of the writer file all stay green (97/98).
   So nothing depends on the resurrection.
   Fix: with a ledger, keep and report a file that is gone. Flip the test into a red-first test
   showing that a foreign delete survives. The no-ledger path can keep the current behaviour.

## Non-blocking (fix if you are in the file)

- `note_status_files_written` reads the status files back in a new lock hold after the emission
  has released its own. A foreign status append that lands in that gap is recorded as finalize's
  and is undone if the run fails. The status guard's own compare-and-swap is the first restore, so
  this window is narrow. Recording inside the emission's hold would close it, for example
  `notify_written` in `store.append_event` with the bytes read under that lock.
- `_flush_one_frontmatter_write`'s fallback `write_frontmatter` (taken when the WP file vanished)
  goes through `FrontmatterManager.write` > `Path.write_text`. That write is neither atomic nor
  ledgered, so if the run fails it is reported as a foreign "kept" file.
- `bake.py`: `original = primary_meta_path.read_bytes()` is read outside the hold that writes. A
  field set between that read and `_locked_assign_mission_number` is lost when the
  compare-and-swap undo succeeds.
- `kernel.atomic.observe_writes`, `stop_observing_writes` and `notify_written` have no direct tests
  in `tests/kernel/test_atomic.py`, and nothing tests the chained-observer (`outer is not None`)
  branch. The diff-cover gate is likely to flag this.

## Verified good

- The kernel hook is acceptable. It uses a `ContextVar` (no process-global state, reset in
  `finally`, and new threads start without an observer) and makes one `.get()` on the hot path.
  `tests/architectural/test_layer_rules.py` passes, and `core/atomic` imports from kernel in the
  allowed direction.
- The ledger catches every finalize write site I found: frontmatter, `tasks.md`, meta, lanes,
  issue matrix, acceptance scaffold, `status.json`/derived views (notified), and events (read-back).
- Cycle-1 reproduction: a foreign note on a WP that finalize never wrote is now kept and reported.
  Reviewer mutation (ledger filter off): 5 tests fail.
- The 16-file import swap is mechanical (`specify_cli.status.mission_write.X` to
  `specify_cli.status.X`). The allowlist additions (`mission_write_lock_dir`, the scaffold's
  locked body) are narrow, and the lock-spy now wraps the real lock. The `git add -A` commit
  (`a510f930e`) contains only files related to this work.
- `review/cycle.py`, `baseline.py`, `runtime_state_cutover.py`, `scaffold_acceptance_matrix` and
  `backfill_ownership` fallback all look right.
- 327 targeted tests pass. ruff and C901 are clean. mypy shows no new errors against `1636aa9bc`.
  There are no new suppressions.
- `ruff format --check` flags `src/runtime/next/runtime_bridge.py` (`5851162a8`, the orchestrator's
  commit) and `tests/runtime/test_pack_runtime_template_parity.py` (WP06). Neither comes from
  WP04.
