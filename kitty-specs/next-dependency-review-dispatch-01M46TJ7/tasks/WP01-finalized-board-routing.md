---
work_package_id: WP01
title: Finalized-board routing — the wedge + advance first-contact parity
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- SC-001
- SC-002
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Runtime routing
history:
- at: '2026-10-05T20:11:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent:
- tests/next/test_next_dependency_wedge_5669.py
- tests/next/test_next_advance_first_contact_5310.py
execution_mode: code_change
model: ''
owned_files:
- src/runtime/next/runtime_bridge.py
- tests/next/test_finalized_task_routing.py
- tests/runtime/test_next_board_authority.py
- tests/integration/test_next_preview_primary_routing.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Finalized-board routing: the wedge + advance first-contact parity

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (resolver-backed) and follow its TDD / type-safety / idiomatic-Python discipline before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix two distinct roots in `src/runtime/next/runtime_bridge.py`, each red-first:

1. **Defect 1 — the wedge (#5669).** `_finalized_task_board_override_step` must report
   `review` (not `implement`) when the only `planned` WPs are dependency-walled and a
   `for_review` WP exists, so BOTH the dispatch path (`_resolve_wp_board_action` →
   `_resolve_wp_board_implement_action`) and the query path
   (`_query_dispatch_decision` → `_build_finalized_override_query_decision`) dispatch the
   pending review. (SC-001, SC-002; FR-001, FR-003.)
2. **#5310 — advance first-contact parity.** Advancing `next` with no persisted run against
   a finalized board must consult the finalized-board authority (agree with query mode),
   not boot a fresh `discovery` run. (SC-003; FR-005.)

**Done when**: on a 2-WP board (`WP02` deps `WP01`, WP01 `for_review`, WP02 `planned`),
`next --result success` returns `kind="step" action="review" wp_id="WP01"` and `next` query
previews the same; with no persisted run on a finalized board, advance and query agree;
all named existing routing tests still pass.

## Context & Constraints

- Spec: `../spec.md`; plan: `../plan.md`; grounding: `../research/code-grounding.md`; charter: `.kittify/charter/charter.md`.
- **C-001 single authority**: gate the override's `planned` arm on the EXISTING
  `discovery.py::preview_claimable_wp` — do not mint a second claimability predicate.
- **FR-002 / #4860 guard**: a dependency-walled `planned` WP must NEVER be dispatched for
  `implement`. Keep the `claimed`/`in_progress`→`implement` resume arms.
- **NFR-002**: `done`/`accept`/`review_in_progress`/`no_actionable_wp` and genuinely-claimable
  `implement` outcomes stay byte-identical. **NFR-003**: no new run-start/git cost on the hot
  path (the extra `preview_claimable_wp` read is idempotent and already performed downstream).
- **No `decision.py` change**: `_implement_state_action`'s for_review fallback is live but
  preempted by the board authority's blocked short-circuit — assert the preemption, don't edit it.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: Defect 1 (the wedge)
- **Purpose**: Pin the wedge through the pre-existing entry points before the fix.
- **Steps**: In `tests/next/test_next_dependency_wedge_5669.py` add `@pytest.mark.regression` (issue-pinned to 5669) tests that build a finalized 2-WP board (WP01 `for_review`, WP02 `planned` with `dependencies:[WP01]`) and assert: (a) `_finalized_task_board_override_step` returns `"review"`; (b) the dispatch path resolves `action="review" wp_id="WP01"`; (c) the query path previews a `review` step (no `dependencies_not_satisfied`). These MUST be RED on the merge-base.
- **Files**: `tests/next/test_next_dependency_wedge_5669.py` (new).
- **Parallel?**: Yes (independent of T003).

### Subtask T002 – Fix: dependency-aware override planned-arm
- **Purpose**: Make the routing authority report `review` for a walled board.
- **Steps**: In `_finalized_task_board_override_step`, gate the `planned` arm on `preview_claimable_wp(...).wp_id is not None` (claimable) rather than bare lane presence; keep `claimed`/`in_progress`→`implement`; let `for_review`→`review` and the endings be reached when the planned WP is walled. Turn T001 GREEN.
- **Files**: `src/runtime/next/runtime_bridge.py`.
- **Parallel?**: No (after T001).

### Subtask T003 – Red-first: #5310 (advance first-contact)
- **Purpose**: Pin the advance/query divergence on a finalized board with no persisted run.
- **Steps**: In `tests/next/test_next_advance_first_contact_5310.py` add an issue-pinned regression asserting advance (`decide_next_via_runtime`) and query (`query_current_state`) resolve the SAME board step on a finalized board with no persisted run. RED on merge-base.
- **Files**: `tests/next/test_next_advance_first_contact_5310.py` (new).
- **Parallel?**: Yes (independent of T001).

### Subtask T004 – Fix: advance first-contact consults the board
- **Purpose**: Make advance honour the finalized board, inheriting T002's verdict.
- **Steps**: Thread the finalized-board authority into the advance first-contact path (`decide_next_via_runtime`/`_dn_bootstrap`) so a finalized board resolves the board step instead of a fresh `discovery` run. Turn T003 GREEN. Keep a genuinely not-started mission (no finalized board) routing to discovery.
- **Files**: `src/runtime/next/runtime_bridge.py`.
- **Parallel?**: No (after T002 and T003).

### Subtask T005 – Verify orchestrator-api shares the seam
- **Purpose**: Ensure no parallel override re-introduces the wedge.
- **Steps**: Confirm `src/specify_cli/orchestrator_api/decision_verbs.py` routes through the same `decide_next_via_runtime`/board authority (no independent claimability/override). If a gap exists, extend coverage; otherwise record the verification in the Activity Log.
- **Files**: read-only verification (+ test if a gap is found).
- **Parallel?**: No.

## Test Strategy

- Targeted only (NO full/heavy suite — CI owns it). Run, at minimum:
  - `tests/next/test_next_dependency_wedge_5669.py`, `tests/next/test_next_advance_first_contact_5310.py`
  - `tests/next/test_finalized_task_routing.py`, `tests/runtime/test_next_board_authority.py`, `tests/integration/test_next_preview_primary_routing.py`
- Prove red→green: each regression RED on the mission `planning_base_branch`, GREEN on the final commit.
- Run `mypy`/`ruff` on the changed files (zero issues; no new suppressions).

## Risks & Mitigations

- Over-gating: gate ONLY the `planned` arm; do not touch the claimed/in_progress resume arms (pre-existing blocked floor must not deepen).
- Query call-site must thread the coord-aware dirs — verify in the query parity test on both `lanes` and `coord` fixtures.
- #5310 remediation must stay a board-authority consult; if it balloons into run-bootstrap machinery, STOP and escalate (keep the Defect-1 change clean).

## Review Guidance

- Red→green witnessed for both defects; #4860 guard intact; NFR-002 byte-identical unaffected cases; no `decision.py` edit; one claimability authority; mypy/ruff clean.

## Activity Log

- 2026-10-05T20:11:52Z – system – Prompt created.
- 2026-10-05 – python-pedro – WP01 implemented (T001-T005), NOT yet moved to for_review.
  - **Defect 1 (#5669, T001/T002):** red `tests/next/test_next_dependency_wedge_5669.py`
    (`@pytest.mark.regression`; override verdict, dispatch authority and query preview all
    reported `implement` on WP01 for_review + WP02 planned deps[WP01]; 3 RED / 3 GREEN-guards).
    Fix: new helper `_has_claimable_planned_wp` (lazy `preview_claimable_wp`, the single
    claimability authority, C-001) gates ONLY the `planned` arm of
    `_finalized_task_board_override_step`; `claimed`/`in_progress`->implement untouched, so a
    walled planned WP falls through to `for_review`->review (#4860 preserved). `decision.py`
    unedited: `test_board_authority_preempts_state_to_action_fallback_for_walled_board` proves
    the board's named blocked_reason short-circuits `_wp_iteration_action_and_state`.
    `tests/next/test_finalized_task_routing.py::_scaffold` gained an optional `dependencies` param.
  - **#5310 (T003/T004):** red `tests/next/test_next_advance_first_contact_5310.py` (advance returned
    the `research`/discovery step while query previewed implement/review/blocked). Fix: new FIRST
    phase `_dn_finalized_board_override` prepended to the `decide_next_via_runtime` phase tuple; it
    calls the shared `_resolve_wp_board_action` and materialises a dispatch via
    `_build_wp_iteration_decision` (reuses the #4980 `mission_state=board_step` rule) or a named
    `blocked:*` as `kind=blocked, mission_state="blocked"` (query parity). Gated on
    `result == "success"` AND an untouched run (`_run_is_untouched`: no completed step, no decision,
    query's own initial-step predicate). First draft (any non-WP current step) broke
    `tests/integration/test_owned_next_runtime.py::...composition_seams...`: a run already walked
    to `tasks` must advance the DAG so run state and decision stay together; narrowed accordingly.
    Declines (accept/done/no finalized board/coord-or-task-surface errors) fall through unchanged.
    Coord analog added in `tests/integration/test_next_preview_primary_routing.py`.
  - **Caveat (accepted, not fixed):** `_dn_bootstrap` still persists a fresh discovery-phase run
    BEFORE the front phase short-circuits; the override preempts it (idempotent, mirrors query's
    ephemeral run). Avoiding the persisted run would need run-bootstrap surgery: out of scope.
  - **Known residual (out of scope):** an all-approved/done finalized board still advances to the
    DAG `research`/discovery step on first contact (board declines accept/done; terminal handling
    stays with `_dn_bootstrap`). Pinned only as "front phase does not dispatch implement/review".
  - **T005 (read-only):** `orchestrator_api/decision_verbs.py::answer_decision` calls
    `runtime.next.decision.decide_next` -> `decide_next_via_runtime`, so it inherits both fixes
    (after an answered decision the run is not untouched, so the front phase correctly skips).
    `orchestrator_api/commands.py::list_ready` is a separate reader that converges on
    `core.dependency_graph.dependency_readiness_for_wp`; the 4 claimability readers
    (override planned-arm via `preview_claimable_wp`, dispatch, query, list_ready) now all resolve
    through `dependency_readiness_for_wp`. No parallel override. No edits there.
  - Evidence: 1362 passed/4 skipped across `tests/next`, runtime bridge/board-authority, owned/next
    integration, orchestrator_api and specify_cli/next suites; `tests/architectural/test_no_dead_symbols.py`
    37 passed. ruff check + format clean, mypy clean on `runtime_bridge.py` and the new tests.
