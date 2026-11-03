# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · t3-code/claude · Seam: create is not mission-bound, so resolve_owned_or_refuse/resolve_owned_mission cannot run (no handle, meta or topology yet). Keep the fix inside resolve_owned_create_root and reuse the leaf's OWNED_CHECKOUT_IS_MISSION_WORKTREE code plus _is_coordination_worktree; the lane leg adds parse_lane_worktree_dir on top of WorktreeTopology.LANE_WORKTREE because classification alone also matches a legitimate owned checkout under .worktrees/.
