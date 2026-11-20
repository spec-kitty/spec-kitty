# Approach

- 2026-11-20: red-first acceptance tests through the real entry points (orchestrator-api app, host accept, move-task) on git fixtures, then the minimal core changes. See plan.md IC-01..IC-03.
- 2026-11-20 (WP01): the red tests failed for the right reasons (no `agent` slot after the API claims; the slots survived an API `--to planned`). Green after the builder, the release helper and the wiring. The blast radius (orchestrator_api, status, every move-task and done-bookkeeping test file: 7631 passed) showed two stale pins, re-pinned out of map: `tests/consolidation/test_merge_done_recording.py` (the reviewer fallback read the implementer's slot) and `tests/status/test_agent_status_emit_aggregate_wiring.py` (an emit claim now records its sidecar).
