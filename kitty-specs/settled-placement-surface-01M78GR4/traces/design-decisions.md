# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-12 · claude-orchestrator · Root cause is not a stale topology read but which checkout holds the resolved ref (settlement makes coordination_branch == mission_branch). Chosen: PlacementSeam.write_dir(kind).surface_root as the one checkout authority (design B). Rejected: routing use_coord by topology+kind (design A) - no #7551 fix, regresses PUBLISHED/landed Missions.

2026-11-12 · claude-orchestrator · WP02: the router's PRIMARY-arm checkout lookup asks the seam with the group's kind only when it is a PRIMARY kind, else with SPEC (declared-PRIMARY write_dir: no side effects, same checkout, because this arm always commits on the primary ref). Asking write_dir(COORD kind) there recursed through establish_coord_write_location -> coord seed commit -> commit_for_mission. Accepted by the orchestrator as within the ruled design B (one seam authority); re-anchored files still translate with their own kind.

2026-11-12 · claude-orchestrator · Cycle hazard (residual): PlacementSeam.read_dir -> resolve_artifact_surface -> resolve_lifecycle_phase (lifecycle_phase.py:271) -> get_feature_target_branch. Any target-branch helper that reads through PlacementSeam.read_dir recurses forever for a consolidated Mission (baseline_merge_commit). #7595 therefore reads through read_dir_for(PRIMARY_METADATA) (operator ruling, escalation 3), pinned by a 0-re-entry regression test; the stale 'read_dir never reaches this' comments are corrected.
