# Decision Moment `01M3H11NX4HRRMNC0NX6394TTH`

- **Mission:** `issue-matrix-partition-integrity-01M3H10A`
- **Origin flow:** `specify`
- **Slot key:** `specify.fix.depth`
- **Input key:** `fix_depth`
- **Status:** `resolved`
- **Created:** `2026-09-27T08:52:29.732181+00:00`
- **Resolved:** `2026-09-27T08:52:31.960566+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How deep should the coordination-partition read fix go?

## Options

- Deep: read the coordination branch ref when the worktree is unmaterialized
- Shallow: adopt existing coord_read_dir_for only
- Other

## Final answer

Deep: resolve coord-partition artifacts (issue-matrix) from the coordination branch ref when the worktree is unmaterialized post-consolidation, so review and merge read authored verdicts correctly even after teardown.

## Rationale

_(none)_

## Change log

- `2026-09-27T08:52:29.732181+00:00` — opened
- `2026-09-27T08:52:31.960566+00:00` — resolved (final_answer="Deep: resolve coord-partition artifacts (issue-matrix) from the coordination branch ref when the worktree is unmaterialized post-consolidation, so review and merge read authored verdicts correctly even after teardown.")
