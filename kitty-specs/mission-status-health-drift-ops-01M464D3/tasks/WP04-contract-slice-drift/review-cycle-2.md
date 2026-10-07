---
affected_files: []
cycle_number: 2
mission_slug: mission-status-health-drift-ops-01M464D3
reproduction_command:
reviewed_at: '2026-10-06T18:55:04Z'
reviewer_agent: user
wp_id: WP04
---

# WP04 rework (operator ruling at WP07, 2026-10-06): an unreachable remote does not end the drift scan

The WP07 review proved on a real repository that the stock resolver answers an unreachable remote by keeping the Mission's own directory, so `GET /drift` returns 200 with no fallback entry. The contract prose says an unreachable remote ends the scan in 500. The operator ruled that the TEXT is fixed to the real behaviour; see the tracer section "Operator ruling at WP07: an unreachable remote does not end the drift scan".

Fix, descriptions only, with no schema shape, enum, required list or response change:
1. `contracts/mission-status/schemas/DriftReport.yaml` (line ~10) and `contracts/mission-status/paths/drift.yaml` (the operation description), plus any other contract prose or CHANGELOG line making the same claim (grep for "unreachable", "network", "500"). State that an unreachable remote leaves the Mission's own directory as the read directory (200, no fallback entry); a reachable remote lacking the branch gives the `coordination_branch_deleted` fallback; any other resolver error is a 500 `drift_scan_unreadable`.
2. Any contract test asserting the old sentence is updated to assert the new one (no loosening: it pins the new text).
3. The ten tools, the negative runner, the breaking check (unchanged: `breaking=4 provisional_changes=1`) and the 1.1 proof module stay green.
