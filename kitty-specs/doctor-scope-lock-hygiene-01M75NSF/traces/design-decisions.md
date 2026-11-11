# Design decisions

See plan.md "Design decisions" D-1..D-11 for the full list. Recorded here as they are made or revised.

- D-1 `--fix` with no scope refuses (non-interactive CLI); Decision Moment 01M75NVX2D22SPCRPWBARSFHPQ.
- D-10 no automatic reclaim of a stale lock: unlinking breaks mutual exclusion (kernel G3). Interpretation the operator
  may overturn.
- D-11 revised during WP02: the reset-obstruction line keeps git's `XY path` prefix (five `ref_advance` tests pin it as
  a contract) and appends the state in words. Spec FR-011 reworded to match.
- WP01: `_resolve_mission_dirs` (root walk) kept, so the walker-gate allowlist entry for `_coordination_doctor.py`
  stays; the off-root sources come from the placement seam (`_read_path_resolver`).
- WP01: the scan's `load_meta` reads were consolidated into one reader (`_read_scanned_meta`), so the census ledger
  lost two rows and gained one.
- WP02: no in-process memo for the exclude: pytest (and any long-lived process) can recreate a repository at the same
  path; `exclude_from_git_index` already writes only a missing line.
