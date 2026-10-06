# Design-decisions tracer

- DD-1: route the composition path through `plan_advance` / `commit_advance` rather than add the two calls to the adapter planner, so one planning authority remains.
- DD-2: the terminal gate seam is the abort-only `before_run_completed` guard, not a wrapping `complete_run(emit)` hook. The engine keeps sole ownership of emitting `MissionRunCompleted` (squad MAJOR 2).
- DD-3: no stale-plan fallback on the composition path. `StaleAdvancePlan` surfaces as the EDGE-003 blocked Decision (FR-001).
- DD-4: the non-blocking retrospective capture runs after the commit, so after `state.json` is written. Before this change it ran before the write. A capture-build failure is now best-effort as well (R-4 #1).
- DD-5: the adapter wraps no engine writer; only the engine's commit writes a run (R-4 #4).
