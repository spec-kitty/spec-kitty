# Tracer: Approach

Mission: Next dependency wedge — dispatch the review (#5669 + folded #5310).

## Plan of attack (seeded at planning; append during implement)
- Three defects, three WPs, single_branch topology, red-first ATDD each.
- **WP01 (Defect 1, #5669):** make `_finalized_task_board_override_step`
  (`src/runtime/next/runtime_bridge.py`) dependency-aware — gate the `planned`
  arm on `preview_claimable_wp`; keep `claimed`/`in_progress` resume arms; let
  the `for_review`→`review` branch be reached when the planned WP is walled.
  One seam fixes both dispatch (`_resolve_wp_board_implement_action`) and query
  (`_build_finalized_override_query_decision`).
- **WP02 (#5310):** make the advance first-contact path consult the
  finalized-board authority instead of booting a fresh `discovery` run
  (`decide_next_via_runtime`/`_dn_bootstrap`). Depends on WP01 (builds on the
  corrected override). Confirm orchestrator-api shares the seam.
- **WP03 (Defect 2, #5669 part 2):** classify `kitty-specs/<slug>/mission-events.jsonl`
  as a review-handoff survivor in `dirty_classifier.py::_is_review_handoff_survivor_path`
  — scoped, NOT the global churn owner. Independent of WP01/WP02.
- Drive implement/review via explicit verbs (not the `next` loop) to avoid
  dogfooding the very wedge into this mission.

## Appended during implement
- 2026-10-05 — WP02 (Defect 2, #5669; T006/T007/T008) done. Red-first:
  `tests/review/test_mission_events_dirty_survivor_5669.py` (`@pytest.mark.regression`)
  pinned the refusal — the positive survivor assertions were RED on HEAD (the log
  classified blocking), the negative controls (`src/app/mission-events.jsonl`,
  `kitty-specs/<slug>/research/mission-events.jsonl`, a real source edit) + the C-002
  guard were already GREEN. Fix: added a function-local, `fullmatch`-anchored
  `re.compile(r"kitty-specs/[^/]+/mission-events\.jsonl$")` survivor to
  `dirty_classifier.py::_is_review_handoff_survivor_path` (mirrors `wp_task_pattern`),
  plus a docstring bullet. 32/32 green in `tests/review/`; agent consumer
  `test_agent_git_paths.py` 34/34 green. C-002 honoured: the global owner
  (`coherence.is_self_bookkeeping_churn`/`is_toolchain_generated_churn`) was NOT
  touched and still returns False for the log. ruff/mypy clean, no new suppressions.
  Red commit 8f906b2, fix commit e89420f.
- 2026-10-05 — WP01 (Defect 1 #5669 + #5310; T001-T005) implemented. Red-first twice:
  `tests/next/test_next_dependency_wedge_5669.py` (3 RED on HEAD: override/dispatch/query all
  `implement`) then fix = `_has_claimable_planned_wp` gating only the override's `planned` arm on
  `preview_claimable_wp`; `tests/next/test_next_advance_first_contact_5310.py` (3 RED: advance
  returned the discovery `research` step) then fix = new first phase `_dn_finalized_board_override`
  over the shared `_resolve_wp_board_action`. A coord analog lives in
  `tests/integration/test_next_preview_primary_routing.py` (drops the fixture's DECOY primary log,
  which forks the coordination seed that advance — unlike query — opens). `decision.py` untouched.
  T005: orchestrator-api `answer_decision` shares `decide_next`; `list_ready` converges on
  `dependency_readiness_for_wp`.

