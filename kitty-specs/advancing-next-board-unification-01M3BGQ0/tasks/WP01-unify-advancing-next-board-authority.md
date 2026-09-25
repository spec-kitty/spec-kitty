---
work_package_id: WP01
title: Unify advancing next with the coord-aware board authority
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
planning_base_branch: fix/advancing-next-board-unification
merge_target_branch: fix/advancing-next-board-unification
branch_strategy: Planning artifacts for this mission were generated on fix/advancing-next-board-unification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/advancing-next-board-unification unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-advancing-next-board-unification-01M3BGQ0
base_commit: 242a0a110b8363910b37d8dccd65b2287f161711
created_at: '2026-09-25T06:01:30.932961+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Unification fix
history:
- at: '2026-09-25T05:40:00Z'
  actor: claude
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/runtime/next/runtime_bridge.py
- src/runtime/next/decision.py
- tests/runtime/test_bridge_parity.py
- tests/next/test_finalized_task_routing.py
- tests/next/test_decision_unit.py
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Unify advancing next with the coord-aware board authority

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make advancing `spec-kitty next --result success` derive the next step/WP from the **same** coord-aware finalized-task-board authority that query mode already uses, so the two modes agree by construction. This closes two P0 release blockers that are two faces of one defect:

- **#4980** — after a review REJECT the WP drops to lane `planned`; advancing `next` spins on `kind=step action=review wp_id=null` (composition placeholder) forever, while query mode says implement/WP01.
- **#4975** — on the default `coord`/`lanes_with_coord` topology advancing `next` blocks `No action mapped for WP step 'implement'` (exit 1) because it reads WP lanes off the primary dir with no coord-aware `status_dir`.

**Done when** every clause of [contracts/advance-query-parity.md](../contracts/advance-query-parity.md) (CT-1…CT-7) is asserted and green, the original #4980 reproduction no longer reproduces (bug arm re-dispatches implement; approve/early controls unchanged), and #4975 coord dispatch works (exit 0, `implement WP01`).

## Context & Constraints

- **Reference behavior = query mode.** `query_current_state` (`src/runtime/next/runtime_bridge.py`) derives the step via `_finalized_task_board_override_step(task_board.read_dir, progress, status_dir=status_state.read_dir)` (coord-aware) then resolves the WP via `preview_claimable_wp(..., status_dir=<coord-aware>)` in `_build_finalized_override_query_decision`. Mirror this for advancing mode.
- **The seam.** Both advancing WP-iteration builders — `_build_wp_iteration_decision` (the `not should_advance` stay-in-step path from `_dn_dependency_gate`) and `_map_wp_step_decision` (the DAG-advance `kind=step` path) — currently call the bare `_state_to_action(step_id, feature_dir, …)` with the *issued* step and no coord-aware `status_dir`. Route both (and the DAG-advance path) through one board-authority-backed action selector.
- **Read first**: [spec.md](../spec.md), [plan.md](../plan.md) (Implementation Strategy), [research.md](../research.md) (parallel-authority inventory + decisions), [data-model.md](../data-model.md), [contracts/advance-query-parity.md](../contracts/advance-query-parity.md), `.kittify/charter/charter.md`.
- **Governance**: ATDD red-first (ADR 2026-07-17-1); single canonical authority (charter principle #1 → NFR-002); coord-read fail-closed (ADR 2026-09-24-2 → NFR-003); decision-layer-only, no engine-state write (NFR-001); complexity ≤15; new branches/helpers get focused tests in the same commit (Sonar new-code gate).

## Branch Strategy

- **Strategy**: coord topology; per-lane worktree from `lanes.json`.
- **Planning base branch**: `fix/advancing-next-board-unification`
- **Merge target branch**: `fix/advancing-next-board-unification` (published via PR to upstream `main`)
- Execution worktrees are allocated per computed lane from `lanes.json`. **Do NOT** drive this mission's own loop via `spec-kitty next --result success` (it hits the very bug you are fixing) — you are already inside the WP01 execution worktree via `spec-kitty implement WP01`.

## Subtasks

### T001 — Red-first regression: #4980 review-reject re-dispatch (single_branch)
**Purpose**: Lock the #4980 defect through the public seam before fixing.
**Steps**:
1. In `tests/runtime/test_bridge_parity.py`, add an issue-pinned `@pytest.mark.regression` test (reference `#4980`) that: drives a `single_branch` mission to a run issued on `review`, rejects WP01 to `planned` (append the `for_review→planned` StatusEvent as `test_finalized_task_routing.py` does), then asserts `decide_next_via_runtime(..., result="success")` returns `kind=step action=implement wp_id=WP01` **and** equals `query_current_state(...)`'s `(action/preview_step, wp_id)`.
2. Assert it is NEVER `kind=step action=review wp_id=null` with the composition placeholder.
3. Run it and **confirm it is RED** on current code; record the failure.
**Validation**: test fails on HEAD for the documented reason (placeholder spin), not a fixture error.

### T002 — Red-first regression: #4975 coord implement dispatch
**Purpose**: Lock the #4975 defect through the public seam.
**Steps**:
1. Add an issue-pinned `@pytest.mark.regression` test (reference `#4975`) driving a `coord` mission to a ready implement step; assert `decide_next_via_runtime(..., result="success")` returns `kind=step action=implement wp_id=WP01` (exit-0 shape), equal to `query_current_state(...)`.
2. Assert it is NOT `kind=blocked reason="No action mapped for WP step 'implement'"`.
3. Run it and **confirm RED** on current code.
**Validation**: fails on HEAD for the coord-blind reason.

### T003 — Full acceptance matrix
**Purpose**: Cover every contract clause / acceptance arm so a branch-by-branch fix can't pass.
**Steps** (all through the public seam, parity + absolute anchor):
1. **Combined coord×review cell** (US3 / CT-2): reject on `coord` and `lanes_with_coord`; assert re-dispatch `implement WP01`.
2. `lanes_with_coord` implement dispatch (CT-3, absolute anchor).
3. Controls: approve → accept→terminal; early-reject (reject while issued on `implement`) → re-dispatch implement; `single_branch`/`lanes` implement dispatch unchanged (CT + FR-006).
4. Multi-WP dependency-order (US1 S5): WP01 rejected while WP02 dependency-gated → re-dispatch only WP01, WP02 order undisturbed.
5. Blocked floor (CT-4): review-step-none / all-in_review / dependency-walled → `kind=blocked` exit 1 with a **named recovery command**; never exit-0 `kind=step`, never WP-less placeholder.
6. Unmaterialized coord (CT-5 / NFR-003): coord surface unmaterialized → typed fail-closed error naming the surface, NOT the generic no-actionable-WP floor. **Fixture**: reuse the ADR 2026-09-24-2 `CoordinationWorktreeUnmaterialized` test helper / fixture from `tests/` (the coord-read-fail-closed suite `mission_runtime.resolution`) — do NOT improvise the unmaterialized condition; find it via `grep -rl "CoordinationWorktreeUnmaterialized" tests/`.
7. Snapshot identity (CT-6 / NFR-001): the persisted run/engine snapshot is byte-identical before/after the re-dispatch call. **Name the exact artifacts compared**: the run-state file(s) under the run dir (`.kittify/runtime/…` run snapshot / `state.json`) AND the engine snapshot the run persists; assert byte-identity on the full set the run writes, not one file (locate them from `next_invocation_lifecycle.py` / the run store; record the paths in the test).
**Validation**: matrix compiles; the arms that exercise the fixed paths are RED pre-fix where applicable.

### T004 — Shared board-authority action selector
**Purpose**: The unification core.
**Steps**:
1. Add one internal selector (in `runtime_bridge.py`) that, given the coord-aware surfaces, returns the advancing `(action, wp_id, workspace)` or a `blocked:*` signal — computing the step via `_finalized_task_board_override_step(task_board, progress, status_dir=<coord-aware>)` and the WP via `preview_claimable_wp(..., status_dir=<coord-aware>)` (implement branch) / the **canonical for_review resolver `_find_first_wp_by_lane(<coord-aware status_dir>, "for_review")`** for the review branch (reuse this existing reader — C-003 forbids minting a fifth lane reader). Resolve the coord-aware `status_dir` via `mission_context_for(repo_root, mission_slug)` exactly as query mode does.
2. Route `_build_wp_iteration_decision` and `_map_wp_step_decision` through the selector instead of the bare `_state_to_action(step_id,…)`; when the board reports a step different from the stale issued `step_id` (e.g. board=implement while issued=review), emit for the board step (this is the re-dispatch).
**Validation**: T001/T002 turn GREEN; complexity ≤15 on the touched functions.

### T005 — Blocked floor + no placeholder + fail-closed
**Purpose**: FR-004/FR-005/NFR-003.
**Steps**:
1. Map `blocked:*` sentinels → `kind=blocked` (exit 1) with the concrete recovery command enumerated per sentinel in contract CT-4 (`no_actionable_wp` → `spec-kitty agent tasks status --mission <slug>`; `review_in_progress` → `spec-kitty agent tasks status --mission <slug>`; dependency-walled → `spec-kitty agent tasks status --mission <slug>`; unmaterialized coord → `spec-kitty doctor workspaces --fix`). Align with any existing blocked-recovery convention already in the codebase if one exists (canonical-source: reuse, don't reinvent). The T003 assertion MUST check the recovery string is a **runnable `spec-kitty` invocation** (parses as a valid command), not merely non-empty.
2. Guarantee a WP-less WP-iteration action never reaches `_build_prompt_or_error`'s composed-marker path.
3. Preserve/propagate the coord-read fail-closed raise (`CoordinationWorktreeUnmaterialized`/`Deleted`) as a named blocked reason, not the generic floor.
**Validation**: T003 blocked-floor + fail-closed arms GREEN.

### T006 — Collapse the divergence (NFR-002) + campsite
**Purpose**: Single authority at the seam; no residual divergent path.
**Steps**:
1. Retire/delegate `_state_to_action`'s WP-iteration step→action logic into the single authority (keep its non-WP/template branches as-is). `_should_advance_wp_step`/`_wp_blocks_step` stay as the leave-step boolean but read the same coord-aware surface.
2. Fold domain-matched debt only: de-duplicate the two identical `_state_to_action` call sites / the "No action mapped for WP step" literal if it lowers complexity. Do NOT decompose the 140 KB file.
**Validation**: two DISTINCT checks — (a) the NFR-002 **negative single-authority test**: assert no advancing WP-iteration/DAG path emits a step/WP the board authority did not produce (drive the public seam across the matrix and assert every advancing `(action, wp_id)` is one the board authority yields for that state); (b) `tests/next/test_finalized_task_routing.py` pins the lane→step mapping. The mapping pin is NOT the negative guard — both are required.

### T007 — Green + closeout
**Purpose**: Land it honestly.
**Steps**:
1. Convert transitional `@pytest.mark.regression` repros to focused parity tests (or a functional home) — do not leave them marked `regression` (ADR 2026-07-17-1).
2. Re-run the **frozen** #4980 reproduction script committed at `kitty-specs/advancing-next-board-unification-01M3BGQ0/repro/repro_4980.sh` (the exact script from issue #4980's "Complete reproduction" block, committed before the fix): confirm the bug arm now re-dispatches implement and approve/early controls are unchanged. Do NOT reconstruct your own post-fix script — run the frozen artifact so the "no longer reproduces" check is non-circular. Confirm #4975 coord dispatch works (`SPK_QA_SOURCE="$PWD" TOPO=coord` variant, or a coord arm).
3. Run the blast-radius tier: `.venv/bin/python -m pytest tests/runtime/test_bridge_parity.py tests/next/ tests/runtime/next/ -q`.
4. Add a `[Unreleased]` entry to `docs/changelog/CHANGELOG.md` (bold impact-first, `(#4980, #4975)` refs, before→after).
**Validation**: blast-radius tier green; original repro no longer reproduces.

## Test Strategy

ATDD red-first per ADR 2026-07-17-1: T001–T003 land RED regressions through the **public** `decide_next_via_runtime` vs `query_current_state` seam (never a private helper — the defect is only visible at the composed decision). After the fix, transitional repros become focused parity tests. Run at the blast-radius tier; do NOT run a whole-repo suite (CI owns breadth).

## Definition of Done

- [ ] CT-1…CT-7 asserted and green (parity matrix incl. combined coord×review cell).
- [ ] **RED-first evidence recorded**: the captured pre-fix failure output for #4980 (placeholder-spin) and #4975 (coord-blind "No action mapped") is surfaced in the review evidence — red-first was observed, not just asserted after the fact.
- [ ] Original **frozen** #4980 repro (`repro/repro_4980.sh`) no longer reproduces; approve/early controls unchanged; #4975 coord dispatch works.
- [ ] One board authority consulted by both WP-iteration builders + the DAG-advance path; no residual bare-`_state_to_action` WP-iteration path — **enforced by the NFR-002 negative single-authority test** (T006), distinct from the mapping pin.
- [ ] No engine-state write (snapshot byte-identity on the named run+engine artifacts, NFR-001); coord-read fail-closed (NFR-003).
- [ ] Recovery command per `blocked:*` sentinel is a runnable `spec-kitty` invocation (asserted, not just non-empty).
- [ ] Transitional `@pytest.mark.regression` repros converted to focused parity tests — none left marked `regression` (ADR 2026-07-17-1).
- [ ] Complexity ≤15 on touched functions; ruff + mypy clean; no new `# noqa`/`# type: ignore`.
- [ ] CHANGELOG `[Unreleased]` entry added.
- [ ] Blast-radius tier green; commands + counts recorded for the review.

## Risks

- **Whack-a-field (#4860 recurrence)** — mitigated by NFR-002 + the combined coord×review acceptance cell.
- **Coord read** — must fail closed, not substitute empty-primary.
- **Dogfooding** — do not drive this mission's own loop via the buggy autonomous `next`.

## Reviewer Guidance

Verify: (a) both WP-iteration builders + DAG-advance consult one authority; (b) combined coord×review cell tested + green; (c) snapshot identity (no engine write); (d) original #4980 repro no longer reproduces; (e) complexity ≤15; (f) transitional regressions converted, not left marked `regression`.
