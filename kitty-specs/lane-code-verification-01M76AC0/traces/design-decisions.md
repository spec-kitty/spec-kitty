# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][research] Bugfix kind, red first through the CLI.** Expected slices: a lane verified-test-invocation seam, implement prints and records it, the pre-review gate records evidence provenance and refuses another tree. Non-goals: no gate weakening, no packs/built-in edits, no consolidation/commit-router/decisions changes.

2026-11-12 · claude-orchestrator · **[2026-11-12][plan] Follow-ups: lane packs filed as #7577; orchestrator-api gate gap NOT filed.** The orchestrator-api for_review gate gap is already owned by #7407 (re-scoped 2026-11-10 to the gate layer, under #7361), so this Mission cites #7407 instead of filing a duplicate.

2026-11-12 · claude-orchestrator · **[2026-11-12][implement] WP03 baseline symmetry broke three tests whose global subprocess doubles now also catch the recipe's git ls-files.** Standing Order 4 judgement: tests valid, doubles over-broad; ruling: narrow the doubles by stubbing lane_invocation.tracked_paths, assertions unchanged, no product workaround (ownership-map leeway, files owned by no WP).

2026-11-12 · claude-orchestrator · **[2026-11-12][review] Review follow-ups to settle at close-out.** WP01: no test pins the probe's -P flag; a lane venv on Python older than 3.11 makes the probe always unverified (strip sys.path[0] inside the probe script instead). WP06: pack_fetch replaces a cache entry non-atomically (pre-existing, now reachable from implement; candidate issue); any packs/*.source.yaml counts as a pin (remedy names make sync-packs).

2026-11-12 · claude-orchestrator · **[2026-11-12][review] WP03 approved; carry into WP04/close-out.** WP04 must map a REFUSE aggregate onto its own exit branch (today should_exit is True with blocked and terminal both False); follow-ups: no test for the uv path with a non-None run_env; tracked_paths in the probe/baseline recipe has no timeout (pass one).
