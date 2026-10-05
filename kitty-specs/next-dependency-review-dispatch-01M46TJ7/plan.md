# Implementation Plan: Next dependency wedge — dispatch the review

**Branch**: `kitty/mission-next-dependency-review-dispatch-01M46TJ7` | **Date**: 2026-10-05 | **Spec**: `./spec.md`
**Input**: Mission specification from `kitty-specs/next-dependency-review-dispatch-01M46TJ7/spec.md`

## Summary

Three defects, one promise: **advancing `next` and querying `next` must agree on a
finalized task board, and neither may wedge when the only actionable work is the review
of a `for_review` WP that a `planned` WP depends on.** Each defect is a small, surgical
fix at a single authoritative seam, landed red-first (ADR 2026-07-17-1):

1. **Defect 1 (#5669)** — the routing authority `_finalized_task_board_override_step`
   (`src/runtime/next/runtime_bridge.py`) returns `"implement"` for a dependency-walled
   `planned` WP, so the `for_review`→`"review"` branch is never reached. Fix: gate the
   `planned` arm on real claimability (`preview_claimable_wp`), keep the
   `claimed`/`in_progress` resume arms, and fall through to `for_review`→`review` when the
   planned WP is walled. One seam fixes both the dispatch path
   (`_resolve_wp_board_implement_action`) and the query path
   (`_build_finalized_override_query_decision`).
2. **#5310 (folded)** — advancing `next` on first contact (no persisted run) boots a fresh
   `discovery` runtime (`decide_next_via_runtime`→`_dn_bootstrap`→`get_or_start_run`)
   instead of consulting the finalized board that query mode honours. Fix: make the
   advance first-contact path consult the finalized-board authority so advance and query
   agree; it inherits Defect 1's corrected verdict.
3. **Defect 2 (#5669 part 2)** — `next` appends `kitty-specs/<slug>/mission-events.jsonl`
   (its own observability log) and leaves it uncommitted, so the move-task dirty gate
   refuses `move-task --to approved` on lanes. Fix: classify that exact path as a
   review-handoff survivor in `dirty_classifier.py::_is_review_handoff_survivor_path`
   (scoped to the review/move-task gate; NOT the global churn owner).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: internal — `src/runtime/next/` (control loop), `src/specify_cli/review/` (dirty gate), `src/specify_cli/status/` (lane reader), `src/mission_runtime/` (placement seam). No new third-party deps.
**Storage**: canonical status event log (`status.events.jsonl`); legacy `mission-events.jsonl`. No schema change.
**Testing**: pytest, targeted surfaces only (NO full/heavy suite locally — CI owns architectural/e2e/perf). Red-first `@pytest.mark.regression` per defect, issue-pinned.
**Target Platform**: CLI, cross-platform (Linux/macOS/Windows).
**Project Type**: single project.
**Performance Goals**: `next` stays within the CLI <2s budget; no added run-start/git cost on the hot path (NFR-003).
**Constraints**: single canonical authority (C-001); `mission-events.jsonl` stays globally non-benign (C-002); ATDD red-first (C-003).
**Scale/Scope**: three functions changed across two modules; ~3 focused WPs.

## Charter Check

*GATE: Must pass before implementation. Re-check after design.*

- **ATDD-first (C-011)** — PASS by construction: each WP lands a failing-first regression (RED on the mission's `planning_base_branch`, GREEN on the fix) before the implementation commit. → C-003.
- **Single canonical authority (DIRECTIVE_044)** — PASS: Defect 1 reuses `preview_claimable_wp` inside the one routing seam (no second claimability predicate); Defect 2 is a scoped per-gate survivor (the global churn owner is deliberately NOT widened — it has live readers + an explicit keep-local ruling). → C-001, C-002.
- **Tiered rigour / DDD** — the `next` control loop is core domain → highest rigour; the dirty gate is glue/IO → still gets a negative-control test.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — PASS: targeted module tests + the specific named gate files only; CI runs the full matrix.
- **Terminology canon** — PASS: "Mission" vocabulary; no `--feature` flags introduced.
- **Branch/version** — no version number assigned in scope; PRs only, operator merges.
- **Red-main discipline** — these are the P1 reds; land the reproductions, fix, no green-washing.

## Project Structure

### Documentation (this mission)

```
kitty-specs/next-dependency-review-dispatch-01M46TJ7/
├── plan.md              # This file
├── spec.md              # Mission spec
├── research/            # Code-grounding findings (brownfield seams)
├── traces/              # tooling-friction / approach / design-decisions
└── tasks.md + tasks/    # /spec-kitty.tasks output
```

### Source Code (repository root)

```
src/runtime/next/
├── runtime_bridge.py          # Defect 1: _finalized_task_board_override_step (routing seam);
│                              #   #5310: decide_next_via_runtime / _dn_bootstrap (advance first-contact)
├── runtime_bridge_io.py       # #5310: get_or_start_run (run bootstrap) — read for context
├── discovery.py               # preview_claimable_wp (claimability authority — reused, not changed)
└── decision.py                # _implement_state_action (live fallback — NOT changed, confirm preempted)

src/specify_cli/review/
└── dirty_classifier.py        # Defect 2: _is_review_handoff_survivor_path (scoped survivor)

src/specify_cli/orchestrator_api/
└── decision_verbs.py          # #5310: verify it shares the next/board seam (no parallel override)

tests/
├── next/test_finalized_task_routing.py      # Defect 1 unit (routing verdict)
├── runtime/test_next_board_authority.py     # Defect 1 dispatch end-to-end
├── integration/test_next_preview_primary_routing.py  # query↔advance parity
├── review/test_dirty_classifier.py          # Defect 2 survivor + negative control
└── (a #5310 regression home chosen at tasks time — advance first-contact vs query)
```

**Structure Decision**: Single project. Edits confined to `src/runtime/next/runtime_bridge.py`
(Defects 1 and #5310) and `src/specify_cli/review/dirty_classifier.py` (Defect 2). No new
modules, no new public symbols beyond what the fixes require.

## Complexity Tracking

No charter violations. The one judgement call (Defect 2 declines the "single global owner"
instinct in favour of a scoped per-gate survivor) is justified under C-002, not a violation:
the global owner has live correctness readers and an explicit keep-local ruling, so widening
it would be the regression.

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Dependency-aware finalized-board routing (the wedge)

- **Purpose**: The finalized-board router must report `review` (not `implement`) when the only `planned` WPs are dependency-walled and a `for_review` WP exists, so both dispatch and query dispatch the pending review.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004; SC-001, SC-002; NFR-001, NFR-002, NFR-003.
- **Affected surfaces**: `src/runtime/next/runtime_bridge.py::_finalized_task_board_override_step` (gate the `planned` arm on `preview_claimable_wp`); it is consumed by `_resolve_wp_board_action` (dispatch) and `_query_dispatch_decision`/`_build_finalized_override_query_decision` (query). Reuses `discovery.py::preview_claimable_wp`.
- **Sequencing/depends-on**: none (foundational).
- **Risks**: must preserve the #4860 guard (a walled WP never dispatched for `implement`); must keep `claimed`/`in_progress`→`implement` (resume) and the `in_review`/`done`/`accept`/`no_actionable_wp` endings byte-identical; double idempotent `preview_claimable_wp` read is acceptable (no new authority). Confirm the query call-site threads the coord-aware dirs.

### IC-02 — Advance first-contact honours the finalized board (#5310)

- **Purpose**: Advancing `next` with no persisted run must consult the finalized-board authority (agreeing with query mode) rather than booting a fresh `discovery` run.
- **Relevant requirements**: FR-005; SC-003; NFR-001.
- **Affected surfaces**: `src/runtime/next/runtime_bridge.py` advance path (`decide_next_via_runtime`/`_dn_bootstrap`); context-read `runtime_bridge_io.py::get_or_start_run`. Verify `src/specify_cli/orchestrator_api/decision_verbs.py` shares the seam (no parallel override).
- **Sequencing/depends-on**: IC-01 (builds on the corrected override verdict).
- **Risks**: distinct root from IC-01 — must not pull the whole run-bootstrap machinery into the Defect-1 change; if the remediation is larger than a board-authority consult, it stays its own WP. Must not regress a genuinely not-started mission (no finalized board → discovery is correct).

### IC-03 — Scoped dirty-gate survivor for `mission-events.jsonl` (lanes approval)

- **Purpose**: `next`'s uncommitted `kitty-specs/<slug>/mission-events.jsonl` must not refuse a `move-task` transition; the exemption must be narrow.
- **Relevant requirements**: FR-006, FR-007; SC-004; C-002.
- **Affected surfaces**: `src/specify_cli/review/dirty_classifier.py::_is_review_handoff_survivor_path` (add the exact-anchored path), consumed via `_is_benign`←`classify_dirty_paths`←`_validate_research_artifacts`←`_validate_ready_for_review` (runs for FOR_REVIEW/APPROVED/DONE).
- **Sequencing/depends-on**: none (independent of IC-01/IC-02).
- **Risks**: must NOT widen `coordination.coherence.is_self_bookkeeping_churn`/`is_toolchain_generated_churn` (destructive consolidate/accept/merge consumers + research-gate readers); must anchor to `kitty-specs/<slug>/mission-events.jsonl` so a user file named `mission-events.jsonl` elsewhere still blocks (negative control). Mirror the function-local-literal pattern the file already uses so the R-014 exemption-registry scan is satisfied.
