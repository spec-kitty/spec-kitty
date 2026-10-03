# Design decisions — rc5-consolidate-regressions

- D1 (#5569): correct the approved-authorship claim (subtract commits reachable from
  fully-canceled lanes) and drop fully-canceled dependency tips from closed-world anchors.
  Rejected: allocator `--no-ff` (new cases only), refusing the cancel (policy change).
- D2 (#5571): reuse `classify_resume_dirty_remedy`/`is_pure_behind_head_lag` for the
  coordination worktree on resume; keep the ancestry-only "already integrated" skip.
- D3 (#5570): compare-and-delete (`update-ref -d <ref> <expected>`) instead of holding
  `feature_status_lock`; smaller and also covers raw git commits.
- D4 (#5572): record strand commit SHAs in the marker at write time; heal refuses on any
  foreign status commit or a legacy marker.
- D5 (tasks): `consolidation/executor.py` is edited by #5571/#5570/#5572 in disjoint functions;
  finalize-tasks forbids overlapping `owned_files`. WP02 owns it; WP03/WP04 depend on WP02 and
  edit only their named executor functions (ownership-map leeway). Trade-off: two parallel waves
  (WP01‖WP02, then WP03‖WP04) instead of strictly one independent lane per WP.
