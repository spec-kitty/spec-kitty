---
affected_files: []
cycle_number: 2
mission_slug: local-event-log-retention-01M5ZCJP
reproduction_command:
reviewed_at: '2026-10-27T21:28:34Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback, cycle 2 (reviewer-renata)

Verdict: changes requested, one narrow defect. Everything else from cycle 1 is resolved and verified:

- (1) FR-008: a recorded `mission_id` resolves by id only; unknown or non-string ids read as
  `Mission not found` and apply leaves the run. The slug is used only when no id is recorded.
  The cycle-1 probe (`collide` run) is now kept.
- (2) A non-mapping run index no longer aborts apply.
- (3) Symlinked run dirs, glossary logs, derived views and the Op index are not collected.
- (4) Items that vanish mid-scan are skipped.
- (5) The index-before-tree order is documented, and a failed rmtree is reported in `failed`.
- All six new tests fail against the pre-fix `retention.py` and pass now.
- No regressions: the BOTH-limits order, the mutation-free preview, the index drop under
  `index_lock`, C-001, FR-013 drift and the reason strings are all unchanged.

## Blocking

1. **A symlinked lock sidecar crashes the preview and aborts apply.** The new `_lock_is_held`
   docstring (`src/specify_cli/state/retention.py`) says "a probe that raises `OSError`
   (permissions, a symlinked lock) reads as held". That is not true for a symlink. The kernel
   lock opens through `open_no_follow`, which raises `kernel.no_follow.NoFollowPathError`. That
   error is a `RuntimeError`, not an `OSError`. Cycle-1 item 5 named this case.
   Reproduced with `/tmp/claude-0/-home-user/c20050d8-f76e-5332-9825-25453e61757d/scratchpad/adv2.py`.
   The setup is two completed runs `a` and `b`, 90 days old, `keep_runs=0`, and
   `runs/a/state.json.lock` is a symlink:
   - **Symlink target exists:** `scan_retention` raises `NoFollowPathError`, so the whole preview
     ends with a traceback. The probe's `with probe:` only catches
     `(LockNotAcquired, OSError)`.
   - **Dangling symlink:** `lock_path.exists()` is False, so the preview marks `a` as a candidate.
     Then `apply_retention` raises `NoFollowPathError` from `try_run_cursor_lock`. That breaks the
     `apply_retention` contract "never abort the loop": `b` is never processed, and the CLI would
     show a traceback. The same path applies to `<log>.lock` beside a glossary log or the Op index
     (`machine_file_lock` in `_delete_locked_log`).

   Nothing is deleted or created outside the repo (O_NOFOLLOW holds), so this fails closed. It is
   still a crash on the case the fix says it covers.

   **Required:**
   - In `_lock_is_held`, read `NoFollowPathError` as `lock held`. Use `lock_path.is_symlink()`,
     or catch the error in both the factory call and the `with probe:` block.
   - In `apply_retention`, record `NoFollowPathError` in `failed` (or `kept_at_apply` as
     `lock held`) and continue the loop.
   - Correct the docstring.
   - Add a red-first test for each of the existing and dangling cases: the preview survives,
     the item is kept as `lock held` (or reported as failed at apply), and the other candidate
     is still deleted.

## Residuals (accepted, record in PR)

- FR-011 guard is path-based (no `git ls-files`).
- `test_no_dead_symbols` red until WP03 adds the CLI caller.
