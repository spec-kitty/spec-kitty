# Tracer: design decisions

- D1-D4 in `research.md`: write through `write_dir(STATUS_STATE)`, resolved outside the best-effort try; one coordination commit at the end of the run via `commit_for_mission(kind=STATUS_STATE)`; fail loud with `SETUP_PLAN_LIFECYCLE_UNCOMMITTED`.
- D5 superseded: the stranded-event report is the existing `COORDINATION_WORKTREE_DIRTY` warning (operator 1A on `01M853E34H1MN0CQGQ9209P8MR`).
- Out of scope: default Mission before settlement (#7827).
