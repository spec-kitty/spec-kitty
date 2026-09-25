# Tasks: Advancing next — task-board authority unification

**Mission**: advancing-next-board-unification-01M3BGQ0
**Branch**: `fix/advancing-next-board-unification` (planning/base) → merge target `fix/advancing-next-board-unification` → published via PR to upstream `main`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Contract**: [contracts/advance-query-parity.md](./contracts/advance-query-parity.md)

One cohesive decision-layer fix in overlapping files (`src/runtime/next/`), so **one work package**, ATDD-ordered internally (red-first regression → unify → green). Splitting would force overlapping `owned_files` and same-lane sequential work with no parallelism gain.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first regression: #4980 review-reject → advance re-dispatches implement (single_branch), public parity seam, `@pytest.mark.regression`, confirmed RED | WP01 | |
| T002 | Red-first regression: #4975 coord implement dispatch, public parity seam, confirmed RED | WP01 | |
| T003 | Full acceptance matrix: combined coord×review cell (US3), lanes_with_coord, approve/early controls, blocked floor (review-none / all-in_review / dependency-walled), unmaterialized-coord fail-closed, snapshot-identity | WP01 | |
| T004 | Shared board-authority action selector; route both WP-iteration builders + DAG-advance path through it (coord-aware `status_dir`, `_finalized_task_board_override_step` + `preview_claimable_wp`) | WP01 | |
| T005 | Route `blocked:*` sentinels → `kind=blocked` + named recovery; no WP-less action reaches the composed placeholder; preserve coord-read fail-closed | WP01 | |
| T006 | Retire/delegate `_state_to_action` WP-iteration divergence into the single authority (NFR-002); campsite-fold duplicated call-site/literal if it lowers complexity ≤15 | WP01 | |
| T007 | Green + closeout: transitional regression → focused parity tests; original #4980 repro no longer reproduces + controls unchanged; blast-radius tier; CHANGELOG `[Unreleased]` entry | WP01 | |

## Work Packages

### WP01 — Unify advancing next with the coord-aware board authority

**Goal**: advancing `next --result success` derives step/WP from the same coord-aware finalized-task-board authority query mode uses; the two modes agree by construction. Closes #4980 + #4975 and their combined cell.

**Priority**: P1 (release blocker, both issues MVP-launch).

**Independent test**: run the #4980 reproduction (bug arm re-dispatches implement post-fix; approve/early controls unchanged) + `tests/runtime/test_bridge_parity.py` parity matrix (all cells incl. combined coord×review) green.

**Included subtasks**: T001, T002, T003, T004, T005, T006, T007 (tracked via `spec-kitty agent tasks mark-status`).

**Implementation sketch** (ATDD order):
1. (T001–T003) Write the red-first regression suite through the **public** `decide_next_via_runtime` (advance) vs `query_current_state` (query) seam; confirm the #4980 and #4975 cases are RED on current code; add the full acceptance matrix (see contract CT-1…CT-7).
2. (T004) Introduce one board-authority-backed action selector; route `_build_wp_iteration_decision` (runtime_bridge stay-in-step) and `_map_wp_step_decision` (DAG-advance) through it with the coord-aware `status_dir` (resolved via the placement seam as query mode does), mapping board→step with `_finalized_task_board_override_step` and board→WP with `preview_claimable_wp`.
3. (T005) `blocked:*` sentinels → `kind=blocked` + named recovery command; guarantee no WP-less action reaches `_build_prompt_or_error`'s composed-marker path; keep the coord-read fail-closed raise (ADR 2026-09-24-2).
4. (T006) Collapse the divergence: `_state_to_action`'s WP-iteration step→action logic delegates to / is retired into the single authority; fold domain-matched debt (duplicate call sites / "No action mapped" literal) if it lowers complexity.
5. (T007) Green the blast-radius tier; convert transitional `@pytest.mark.regression` repros to focused parity tests; confirm the original #4980 script no longer reproduces and #4975 coord dispatch works; add the CHANGELOG `[Unreleased]` entry.

**Dependencies**: none.

**Risks**:
- **Whack-a-field (#4860 recurrence)**: patching only the review branch / only threading `status_dir` leaves two authorities. Mitigation: NFR-002 single-authority-at-the-seam + the combined coord×review acceptance cell (CT-7, US3).
- **Coord read**: the coord-aware read must fail closed, not substitute empty-primary (NFR-003 / CT-5).
- **Dogfooding hazard**: this mission is itself coord topology — do NOT drive its own implement/review via the buggy autonomous `next --result success` loop; use `spec-kitty implement WP01` directly.

**Reviewer guidance**: verify (a) both WP-iteration builders + the DAG-advance path consult one authority (no residual bare `_state_to_action` WP-iteration path), (b) the combined coord×review cell is tested and green, (c) no engine-state write (snapshot identity), (d) the original #4980 repro no longer reproduces, (e) complexity ≤15 on touched functions.

**Estimated prompt size**: ~320 lines.

**Prompt**: [tasks/WP01-unify-advancing-next-board-authority.md](./tasks/WP01-unify-advancing-next-board-authority.md)
