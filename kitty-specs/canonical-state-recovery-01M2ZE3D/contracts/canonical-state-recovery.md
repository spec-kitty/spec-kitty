# Contracts — Canonical-State Integrity & Recovery (#4758, #4786)

The behavioral contracts this mission establishes. Each is enforced by the cited tests.

## C1 — Wedge predicate (single authority)
`lanes.persistence.is_execution_wedged(*, execution_has_begun, lanes_present) -> bool` is the ONE definition of the #4758 anti-state (execution began AND `lanes.json` absent). Consumed by the finalize refusal and the `doctor mission-state --fix` recovery detector. Pure, no I/O.

## C2 — Legacy finalize never half-finalizes (#4758)
`agent tasks finalize-tasks` writes `lanes.json` (via the pure `lanes.compute_and_persist.compute_and_write_lanes`) alongside the event-log bootstrap for ownership-bearing WPs; ownerless WPs are a documented no-op. It never seeds events without lanes. Test: `tests/cli/test_tasks_finalize_lanes_minting.py`.

## C3 — move-task planned-boundary guard (#4758)
`move-task` refuses to move a WP out of `planned` when `lanes.json` is absent (coord/lanes topologies), naming `spec-kitty doctor mission-state --fix --mission <slug>`. Test: `tests/cli/test_move_task_planned_guard.py`.

## C4 — Canonical-state recovery (#4758)
`spec-kitty doctor mission-state --fix --mission <slug>` rebuilds `lanes.json` from the event log when the wedge predicate holds, recording the captured target-branch tip as `planning_commit_sha` (so `--owned-checkout` review resolves). Never rewrites existing lanes (#3311); corrupt log fails closed; ownerless mission handled coherently; idempotent. Tests: `tests/unit/migration/test_mission_state_lanes_rebuild.py`, `tests/integration/migration/test_wp03_advance_to_approval.py`.

## C5 — Implementer attribution is derived, not stored (#4786)
`status.reducer._project_implementer_attribution` derives `implementer_of_record` from the immutable claim event's `policy_metadata` sidecar — read-only, surviving the live-claim release. The accept gate reads the derived slot; a never-owned WP yields nothing and is honestly refused with a named repair. The live `agent` slot's release/suppression (#4673) is untouched. Tests: `tests/status/test_implementer_attribution_projection.py`, `tests/acceptance/test_accept_gate_rejection_cycle.py`.

## Binding invariant
Every gate that refuses names a repair path; every repair path re-establishes the field the gate reads.
