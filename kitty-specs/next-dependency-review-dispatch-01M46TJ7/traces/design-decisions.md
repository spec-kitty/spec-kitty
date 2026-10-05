# Tracer: Design Decisions

## D1 — Defect 1 fix lives in the one routing seam (C-001)
`_finalized_task_board_override_step` is the single routing authority BOTH the
dispatch path and query path consult. Gating the `planned` arm there (reusing
`preview_claimable_wp`, not a new predicate) fixes both at once and keeps a
single claimability authority. Rejected: duplicating a for_review fallback in
both `_resolve_wp_board_implement_action` and `_build_finalized_override_query_decision`
(two authorities, drift risk).

## D2 — Defect 2 is a SCOPED survivor, not the global churn owner (C-002)
Grounding (paula-patterns lens) flipped the initial instinct. `mission-events.jsonl`
has LIVE correctness readers (`runtime_bridge_composition.py` research-gate
primitives) and an explicit "keep it local" ruling in `implement_cores.py:318-332`.
Adding it to `is_self_bookkeeping_churn` would make uncommitted gate rows
discardable by ~41 consumers incl. destructive consolidate/accept/merge. So the
fix is the per-gate survivor list `_is_review_handoff_survivor_path`, anchored to
`kitty-specs/<slug>/mission-events.jsonl`. Deferred canonical-owner consolidation
noted in PR body (adjacent home: #2907); not filed.

## D3 — #5310 is a distinct root in the same module, folded not merged
#5310 is the advance first-contact bootstrap bypassing the board; #5669 Defect 1
is the override's verdict. Separate WPs; WP02 depends on WP01 so the two compose.
If #5310's bootstrap remediation balloons beyond a board-authority consult, it
stays its own WP and does not contaminate the Defect-1 change.

## D4 — #4860 guard preserved
A dependency-walled planned WP must still never be dispatched for `implement`.
The planned-arm claimability gate is consistent with #4860, not a reversal.

## Appended during implement
- (see below)

### D5 — #5310 stays a routing front phase, scoped to an untouched run (WP01, 2026-10-05)
Decision: prepend `_dn_finalized_board_override` to the `decide_next_via_runtime` phase tuple; it
consults the SHARED `_resolve_wp_board_action` (no re-derived claimability, no 5th authority) and
materialises through `_build_wp_iteration_decision` / a named `blocked` Decision. It fires only for
`result == "success"` on an *untouched* run (query's own initial-step predicate: no completed step,
no decision). Rejected alternative A (any non-WP current step): pre-empts a run mid-DAG (e.g. at
`tasks`) so the issued decision outruns the persisted run state (caught by
`test_owned_next_runtime::...composition_seams...`). Rejected alternative B (move the check ahead of
`get_or_start_run`): run-bootstrap surgery, out of scope per the brownfield scout.
Accepted caveat: `_dn_bootstrap` persists a fresh discovery-phase run before the front phase
short-circuits; the override preempts it idempotently, mirroring query's ephemeral run.
Known residual: all-approved/done finalized boards still resolve to the DAG first step on
first-contact advance (the authority declines accept/done by design; `_dn_bootstrap` owns terminal).

