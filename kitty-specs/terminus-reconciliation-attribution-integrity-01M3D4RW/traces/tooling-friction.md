# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-25 · claude · Coord-topology mission's decision-moment + tracer writes during SPECIFY fail with CoordinationWorktreeUnmaterialized (mission_runtime/resolution.py:1977 _classify_artifact_surface) — a READ-classify guard that fires before the commit_router self-materialize path. The exception advises 'spec-kitty doctor workspaces --fix' but that only clears husks (reported 'No workspace husks found') and does NOT materialize; worse, 'doctor coordination --fix' flattened 28 UNRELATED missions' stale coordination_branch keys (reverted). Materialized manually via canonical CoordinationWorkspace.resolve(repo, slug, mid8). Candidate upstream gap: specify-time coord writes should self-materialize, and the exception guidance is misleading.
