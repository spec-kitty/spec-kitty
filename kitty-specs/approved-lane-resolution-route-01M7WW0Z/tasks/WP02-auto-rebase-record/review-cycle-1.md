---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:20:08Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP02
---

# WP02 review feedback (cycle 1) — reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commit de38bfcd

## Verified, no change needed
- Red-first against the de38bfcd^ sources: 30 failed, 2 passed. The 2 passes are the labelled controls. Correct the add-history note, which says "24/2".
- Post-fix: 32/32. tests/lanes + lane_cleanup + integration lane_lifecycle_sync: 1289 passed.
- ruff, format, mypy and C901 are clean. C-002 holds.
- These design points are sound: 40- and 64-hex SHAs accepted; an unexpected parent shape halts without recording; `is_recorded` raises on a foreign value; nested-lane listing filtered; cleanup only after a confirmed delete; the undo uses the guarded reset and re-records the tip.

## Must fix
1. CI red: `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` flags `auto_rebase_record::{AUTO_REBASE_REF_PREFIX, delete, is_recorded, record_ref, recorded_merges}`.
   - Drop them from `__all__` until a consumer exists. WP03 consumes `delete`; WP05 consumes `is_recorded` and `recorded_merges`.
   - `record_ref` and `AUTO_REBASE_REF_PREFIX` may stay module-internal.
   - Run the gate and make it green. No allowlist.
2. (MED, integrity) The record certifies a merge commit whose tree the tool did not produce.
   - `conclude_in_progress_op` and `_finalize_auto_rebase` run a plain `git commit`. That runs the repository's `pre-commit` hook. A hook that stages a file puts that file in the merge commit, and the parent check still passes.
   - Fix, fail closed: in both commit paths, capture `git write-tree` of the index the tool staged, immediately before the commit. Record only if `git rev-parse HEAD^{tree}` equals it.
   - On a mismatch, take the same route as a failed record write: guarded reset to `before`, re-record the tip, and halt with a reason that names the hook-altered tree. If the reset is refused, the merge stays unrecorded and is judged as a hand merge.
   - Add a real-git test with a staging `pre-commit` hook. Assert: no record, the lane is back at `before`, and `halt_reason` names it. Cover both the clean and the auto-resolved shape.

## Routed elsewhere (orchestrator ruling, not WP02)
- The forgeable local ref and lane-committed `.gitattributes` affecting the auto-rebase merge go to WP05: a recorded merge is exempt from RESOLUTION_MERGE_UNREVIEWED only when the FR-010 guard passes with the committed-tree rule. WP05 also tests that a forged record leaves no unreviewed content able to land.
