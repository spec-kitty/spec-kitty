# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude-orchestrator · Root cause is not a stale topology read but which checkout holds the resolved ref (settlement makes coordination_branch == mission_branch). Chosen: PlacementSeam.write_dir(kind).surface_root as the one checkout authority (design B). Rejected: routing use_coord by topology+kind (design A) - no #7551 fix, regresses PUBLISHED/landed Missions.
