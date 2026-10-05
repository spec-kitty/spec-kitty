# Code-Grounding (brownfield seams, verified on main @ 30a152d8)

Grounded via codegraph + a profile-loaded paula-patterns lens and two planner-priti
related-ticket lenses. Verbatim source read; line numbers verified on-disk.

## Defect 1 — the wedge (IC-01)
- `src/runtime/next/runtime_bridge.py::_finalized_task_board_override_step` (736-776).
  Lines 759-764 return `"implement"` on any planned/claimed/in_progress WP BEFORE the
  for_review→`"review"` check at 765-766. A dependency-walled `planned` WP therefore pins
  the override to `"implement"` while a sibling sits in `for_review`.
- Dispatch consumer: `_resolve_wp_board_action` (3434) → override at 3508 → `"implement"`
  → `_resolve_wp_board_implement_action` (3381) → `preview_claimable_wp` (3398) returns
  None (walled) → hard blocked floor (3399-3404). `_wp_iteration_action_and_state` returns
  on `blocked_reason` and never falls through to decision.py's live fallback.
- Query consumer: `_query_dispatch_decision` (3131) → `_build_finalized_override_query_decision`
  (2786) → `preview_claimable_wp` (2821) None → mission_state="implement",
  reason=selection_reason (`dependencies_not_satisfied`).
- Claimability authority to REUSE: `src/runtime/next/discovery.py::preview_claimable_wp`
  (196) — dependency-aware; already called by both consumers. Gate the override's planned
  arm on it; do NOT mint a second predicate (C-001).
- `src/runtime/next/decision.py::_implement_state_action` (441-473) STILL has the
  for_review fallback (459-467) and is LIVE (FR-006 fallback) but PREEMPTED by the board
  authority's blocked short-circuit. No change needed there; confirm preemption in a test.
- #4860 guard: a walled planned WP must never be dispatched for implement — the
  claimability gate is consistent with it.
- Test homes: `tests/next/test_finalized_task_routing.py` (override verdict unit),
  `tests/runtime/test_next_board_authority.py` (dispatch), `tests/integration/test_next_preview_primary_routing.py` (query parity).

## #5310 — advance first-contact (IC-02)
- Flow: `decide_next_via_runtime` (2723) → `_dn_bootstrap` (1718) → `get_or_start_run`
  (1488 → runtime_bridge_io.py:842) starts a fresh run on first contact; query mode
  applies the override, advance boots `discovery` → the two disagree. Distinct root from
  Defect 1 (the override's verdict), same module.
- Verify `src/specify_cli/orchestrator_api/decision_verbs.py` shares the next/board seam
  (no parallel override) — one explicit grep at implement time.
- Brownfield scout owed on `_dn_bootstrap`/`_dn_composition_dispatch`/`_dn_decision_materialize`
  before IC-02 implement (least-grounded surface).

## Defect 2 — lanes approval residue (IC-03)
- Appender: `src/runtime/next/next_invocation_lifecycle.py::emit_mission_next_invoked`
  (303-351) appends `kitty-specs/<slug>/mission-events.jsonl` (STATUS-namespace, tracked,
  write-only for lifecycle rows), left uncommitted.
- Gate: `_validate_ready_for_review` (`tasks_parsing_validation.py:943`) runs for
  `target_lane in (FOR_REVIEW, APPROVED, DONE)` (confirmed tasks_move_task.py:1052) →
  `_validate_research_artifacts` (309) → `classify_dirty_paths` → `_is_benign` →
  `is_toolchain_generated_churn` ∪ `_is_review_handoff_survivor_path`.
- `mission-events.jsonl` is NOT a MissionArtifactKind (residue leg misses it) and NOT in
  `is_self_bookkeeping_churn` → classified blocking.
- DO NOT widen the global owner `coordination/coherence.py::is_self_bookkeeping_churn`
  (60-162): it feeds ~41 consumers incl. destructive consolidate/accept/merge, and
  `mission-events.jsonl` has LIVE readers (`runtime_bridge_composition.py:389-452`
  research-gate primitives) + an explicit keep-local ruling (`implement_cores.py:318-332`).
  Scoped fix only: `dirty_classifier.py::_is_review_handoff_survivor_path` (45-122),
  anchored to `kitty-specs/<slug>/mission-events.jsonl`, function-local literal (R-014).
- Test home: `tests/review/test_dirty_classifier.py` (survivor + operator-file negative control).
- Deferred canonical-owner consolidation → PR body note; adjacent home #2907 (no ticket filed).
