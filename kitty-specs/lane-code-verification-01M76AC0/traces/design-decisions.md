# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-11 · claude-orchestrator · **[2026-11-11][research] Bugfix kind, red first through the CLI.** Expected slices: a lane verified-test-invocation seam, implement prints and records it, the pre-review gate records evidence provenance and refuses another tree. Non-goals: no gate weakening, no packs/built-in edits, no consolidation/commit-router/decisions changes.

2026-11-12 · claude-orchestrator · **[2026-11-12][plan] Follow-ups: lane packs filed as #7577; orchestrator-api gate gap NOT filed.** The orchestrator-api for_review gate gap is already owned by #7407 (re-scoped 2026-11-10 to the gate layer, under #7361), so this Mission cites #7407 instead of filing a duplicate.

2026-11-12 · claude-orchestrator · **[2026-11-12][implement] WP03 baseline symmetry broke three tests whose global subprocess doubles now also catch the recipe's git ls-files.** Standing Order 4 judgement: tests valid, doubles over-broad; ruling: narrow the doubles by stubbing lane_invocation.tracked_paths, assertions unchanged, no product workaround (ownership-map leeway, files owned by no WP).
