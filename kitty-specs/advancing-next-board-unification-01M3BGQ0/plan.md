# Implementation Plan: Advancing next — task-board authority unification

**Branch**: `fix/advancing-next-board-unification` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/advancing-next-board-unification-01M3BGQ0/spec.md`

## Summary

Make advancing `spec-kitty next --result success` derive the next step/WP from the **same** coord-aware finalized-task-board authority that query mode already uses, so the two modes agree by construction. This closes both P0 faces of one defect: the review-branch step-regression (#4980 — a rejected WP dropped to `planned` is never re-dispatched; the loop spins on a WP-less composition placeholder forever) and the implement-branch coord-blindness (#4975 — advancing `next` reads WP lanes off the primary dir with no coord-aware `status_dir`, so it blocks "No action mapped for WP step 'implement'" on the default topology). The fix is **decision-layer only** — no persisted run/engine state is written and there is no DAG regression; the issued step marker stays put and the actionable action is recomputed from the board each call.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: none new — internal only (`src/runtime/next/`, `src/mission_runtime/` placement seam, `spec_kitty_events`/`spec_kitty_tracker` public imports already in use)
**Storage**: append-only status event log (`status.events.jsonl`) via the coord-aware status surface; no schema change
**Testing**: pytest (`tests/runtime/test_bridge_parity.py` primary home; `tests/next/test_finalized_task_routing.py`, `tests/next/test_decision_unit.py`, `tests/runtime/next/`)
**Target Platform**: Linux/macOS/Windows CLI (spec-kitty-cli)
**Project Type**: single (CLI/runtime library)
**Performance Goals**: no new whole-suite cost; blast-radius tier (`tests/runtime/`, `tests/next/`) under ~90s locally (NFR-004)
**Constraints**: decision-layer-only (no engine-state write — NFR-001); single board authority at the shared action-selection seam (NFR-002); coord-read fail-closed per ADR 2026-09-24-2 (NFR-003); complexity ≤15; new branches/helpers get focused tests in the same commit (Sonar new-code gate)
**Scale/Scope**: ~2 source files (`src/runtime/next/runtime_bridge.py`, `src/runtime/next/decision.py`) + regression tests; one cohesive change

## Constitution Check

*GATE: charter (compact mode). Re-checked after Phase 1.*

- **Single canonical authority** (governing principle #1): the fix's core — collapse the divergent advancing/query step-derivation to one board authority. PASS by design (NFR-002).
- **ATDD-first / red-first** (standing order #4, ADR 2026-07-17-1): each issue lands an issue-pinned `@pytest.mark.regression` repro RED through the public seam before the fix; transitional repros become focused parity tests after. PASS (C-001, C-002).
- **Architectural alignment**: change stays inside the `runtime` module's decision layer; consumes the `mission_runtime` placement seam already used by query mode; introduces no new module edge. PASS.
- **Campsite cleaning** (standing order #2): `runtime_bridge.py` is a god-file (140 KB); scope is narrow, so fold only *domain-matched* debt in the touched functions (e.g. de-duplicate the two identical `_state_to_action` call sites / "No action mapped" literals if it lowers complexity), do NOT decompose the whole file. Freeze the rest as baseline.
- **Supply-chain**: no dependency added/upgraded/removed → section N/A (documented in research.md).
- **Terminology guard**: Mission/WP/lane canonical; no `feature*` aliases introduced.

No violations require Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/advancing-next-board-unification-01M3BGQ0/
├── plan.md              # This file
├── research.md          # Phase 0 output (seam analysis, parallel-authority inventory, decisions)
├── data-model.md        # Phase 1 output (decision-envelope + board-authority entities)
├── quickstart.md        # Phase 1 output (how to reproduce + verify)
├── contracts/
│   └── advance-query-parity.md   # behavioral contract: advancing decision == query decision
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/runtime/next/
├── runtime_bridge.py    # _dn_dependency_gate (:1787), _build_wp_iteration_decision (:2937),
│                        #   _map_wp_step_decision (:3047), _finalized_task_board_override_step (:662),
│                        #   _should_advance_wp_step (:745) + _wp_blocks_step (:826)
├── decision.py          # _state_to_action (:394) — the advancing authority to unify/retire-into-one
└── discovery.py         # preview_claimable_wp — canonical coord-aware claimable-WP resolver (reuse)

tests/
├── runtime/
│   ├── test_bridge_parity.py     # PRIMARY red-first home (public decide_next_via_runtime vs query_current_state)
│   └── next/                     # advance-guard tests
└── next/
    ├── test_finalized_task_routing.py  # board-authority lane→step mapping fixtures
    └── test_decision_unit.py           # _state_to_action unit
```

**Structure Decision**: single project; the change is confined to `src/runtime/next/` (the canonical mission control loop) and its mirrored tests. No new files/modules required beyond possibly one small internal helper for the shared action-selection seam.

## Implementation Strategy (the unification)

**Reference behavior = query mode.** Query mode (`query_current_state`, `runtime_bridge.py:2718`) derives the actionable step via `_finalized_task_board_override_step(task_board.read_dir, progress, status_dir=status_state.read_dir)` (`:2776`) — coord-aware — then resolves the WP via `preview_claimable_wp(..., status_dir=<coord-aware>)` (`_build_finalized_override_query_decision`, `:2530-2542`). This is correct today for both the rejected-`planned` case (board → `implement`) and the coord case (coord-aware `status_dir` sees the lane rows).

**The single seam.** Both advancing WP-iteration builders — `_build_wp_iteration_decision` (`:2937`, the `not should_advance` stay-in-step path from `_dn_dependency_gate`) and `_map_wp_step_decision` (`:3047`, the DAG-advance `kind=step` path) — currently call the bare `_state_to_action(step_id, feature_dir, …)` with the *issued* step and no coord-aware `status_dir`. Route both through one board-authority-backed action selector that:

1. Computes the board step with the coord-aware authority (`_finalized_task_board_override_step`, given the coord-aware `status_dir` — resolved from `mission_context_for(repo_root, mission_slug)` exactly as query mode does at `:2534`, or threaded from `_dn_dependency_gate` which already holds `status_dir` at `:1614`).
2. If the board step is `implement` or `review` → resolve the actionable WP via the coord-aware `preview_claimable_wp` (implement) / for-review lookup (review) and emit `kind=step action=<board step> wp_id=<wp>` — this re-dispatches the rejected WP (#4980) and dispatches the coord WP (#4975), overriding a stale issued `step_id`.
3. If the board step is a `blocked:*` sentinel (`blocked:no_actionable_wp`, `blocked:review_in_progress`) → emit `kind=blocked` (exit 1) with a concrete named recovery command; never fall into `_build_prompt_or_error`'s composed-marker path for a WP-less action (FR-004/FR-005).
4. Preserve the coord-read fail-closed policy: the coord-aware read raises the typed error on an unmaterialized/deleted coordination surface (ADR 2026-09-24-2); it is surfaced as a blocked reason naming the unmaterialized surface, NOT collapsed into the generic no-actionable-WP floor (NFR-003).

**Anti-parity discipline (NFR-002).** Do NOT patch the review branch of `_state_to_action` and thread `status_dir` in isolation (that reproduces #4860's branch-by-branch near-miss and leaves the combined coord×review cell diverging). The board authority must be the single source both WP-iteration builders + the DAG-advance path consult; `_state_to_action`'s per-branch step→action logic is retired into (or delegates to) that authority for the WP-iteration steps. `_should_advance_wp_step`/`_wp_blocks_step` (the stay/leave boolean) stays as the "should we leave this step" gate but must read the same coord-aware surface.

**Decision-layer-only (NFR-001).** The selector reads the board and returns an envelope; it writes no run/engine state. The `not should_advance` path already deliberately does not call `next_step()`; the issued step marker is unchanged. A test asserts the persisted run/engine snapshot is byte-identical before/after the re-dispatch call.

## Parallel Work Analysis

**Single sequential lane — no parallelism.** The fix is one cohesive decision-layer change in overlapping files (`runtime_bridge.py`, `decision.py`, shared test files). Splitting it across parallel lanes would race on the same write-scope (shared-root `.git/index.lock`) and invite whack-a-field. One work package, ATDD-ordered internally (red-first regression → unify → green).

- **Sequential work**: red-first regression suite (all six acceptance arms) → the unification → confirm green + original repro no longer reproduces.
- **Parallel streams**: none.
- **Dogfooding note (critical):** this mission is itself `coord` topology; driving its OWN implement/review via the buggy autonomous `spec-kitty next --result success` loop would hit #4975/#4980. Orchestrate implement/review via `spec-kitty implement WP##` directly (the supported workspace prep) and manual review dispatch — not the autonomous loop.

## Complexity Tracking

*No Constitution Check violations to justify.*
