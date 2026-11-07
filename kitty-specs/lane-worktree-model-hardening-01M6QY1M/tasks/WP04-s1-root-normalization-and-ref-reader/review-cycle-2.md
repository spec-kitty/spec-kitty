---
affected_files: []
cycle_number: 2
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T12:17:25Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP04
---

# WP04 review (reviewer-renata), cycle 2: changes requested

## Blocking

**Issue 1: a `read_event_log` caller that relied on fail-open was missed. Two consolidation tests are red on the lane and green on the base.**

`consolidation/done_bookkeeping.py::_durable_coordination_lanes` (line ~679) reads
`read_event_log(EventLogReadContract.coordination_branch_ref(...))`. Its documented contract
(docstring lines ~650-655, and `_durable_done_wps_on_coordination_ref` / `_reconcile_completed_wps_for_resume`)
says: "Returns `None` when the coordination ref cannot be resolved or carries no committed events
(a non-coord topology or a legacy Mission). The caller then falls back to the transactional on-disk check."
Since 552c6e6849 that arm raises `StatusSurfaceRefUnreadable`, so `consolidate --resume` progress
reconciliation now crashes where it used to fall back.

Reproduction (lane worktree):
`PYTHONPATH=$PWD/src python -m pytest tests/consolidation/test_merge_recovery.py::TestEventDedupGuard -q`
gives 2 failed, 4 passed (`test_reconcile_completed_wps_drops_missing_done_evidence`,
`test_reconcile_completed_wps_keeps_existing_done_evidence`:
`StatusSurfaceRefUnreadable ... from ref 'main' ... fatal: not a git repository`). The same command on
the base (`issue-7276-lane-worktree-hardening`, repository root checkout) gives 6 passed.
This is the "hidden callers of read_event_log that expect [] on error" risk the WP names. 14c77d8a99
fixed `coherence.coord_incoherent_done_wps` but not this caller. `tests/consolidation` was not in the
recorded blast radius.

Fix (smallest diff, same shape as the coherence arm):
- Give `_durable_coordination_lanes` the same declared "ref does not exist" arm: return `None` (the
  documented on-disk fallback) when the ref does not resolve. Let a ref that exists but cannot be read
  still raise `StatusSurfaceRefUnreadable`. Decide explicitly, and say in the docstring, what a
  non-repository `repo_root` means. The test fixture is a non-git `tmp_path`; either keep that arm
  returning `None` or move the fixture to `git init` with a written rationale. Do not swallow
  `StatusSurfaceRefUnreadable` wholesale.
- Do not copy `coherence._ref_exists`. Give it one home that both callers import, for example a
  `ref_exists(repo_root, ref)` beside `read_status_ref` in `status_service.py`. Two private copies are a
  duplicate authority.
- Add `tests/consolidation/test_merge_recovery.py` and `tests/consolidation/test_done_bookkeeping_rollback_coherence.py`
  to the recorded blast radius. Re-grep `read_event_log(` / `read_event_stream_log(` and list each caller's
  disposition in the completion summary.

## Verified (no action needed)

- Provenance: be69f5104a is #6884's test alone. It is byte-identical to the upstream tip, with `-x` and
  the `Co-authored-by: Ivan Melck` trailer, and is red on its own commit. The carried `_canonical_status_read_root`
  at 584d104c04 is byte-identical to upstream b950373e8b. No `kitty-specs/lane-worktree-status-shadow-*`,
  CHANGELOG.md or body6466.md paths were carried.
- Red-first at 55263d960d: 7 failed plus the ref-reader collection error, as claimed. Both #6884 tests
  are flipped on purpose, and the commit message says so. Fail-closed matches ADR 2026-11-06-2
  "Root normalization".
- Performance: measured with a subprocess counter. `agent tasks status` makes 2 normalizations and 2-3
  `git worktree list` calls. `next` (query mode, from the repository root) makes 8 normalizations,
  8 `git worktree list` calls and ~45 ms in total, about 5.6 ms each with 6 worktrees. That is not
  material against the < 2 s budget. NFR-001 concerns ref reads, and `read_status_ref` is one
  `cat-file --batch`.
- Ref reader: ABSENT versus missing/ambiguous ref versus git failure are distinguished. The ref and
  path travel on stdin, so no option injection is possible.
- Out-of-map edits are minimal and match the recorded list.
- The three classified failures:
  - test_reassess_under_lock: an environmental source mismatch. The subprocess resolves the root
    checkout's editable install. It passes on the base.
  - test_coord_seed: passes on both the base and the lane here, so it is a timing flake.
  - test_no_dead_symbols: 37 passed serially on the lane.
- New symbols outside `__all__`: justified. All of them have live src callers through
  `read_event_log` / `_read_ref_events_text`, so this is not dead code.

## Non-blocking (fold in if cheap, otherwise trace)

1. Duplicate normalization: `resolve_status_surface_with_anchor` normalizes and then calls
   `candidate_feature_dir_for_mission`, which normalizes again, so 2 `git worktree list` per call.
   Consider a per-process memo keyed on the resolved root, or pass the already normalized root.
   WP05 can take this.
2. A missing tree object under a resolvable commit makes `cat-file` report `<ref>:<path>` as
   "missing", which reads as ABSENT (empty history). This is only possible in a corrupt repository.
   Note it as a residual.
3. The `git init` fixture change in 14c77d8a99 (test_committed_authority) is no longer required after
   4b93e01b7b. It is harmless; keep it.
4. HEAD-less `.git` treated as no repository: low risk. A lane root always carries a `.git` file, so a
   lane root can never be classified "not a repository".
