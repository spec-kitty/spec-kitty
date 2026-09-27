# Implementation Plan: Rejection feedback reaches the implementer

**Branch**: `issue-4899-review-feedback-to-implementer` | **Date**: 2026-09-27 | **Spec**: `kitty-specs/review-feedback-to-implementer-01M3GKZ8/spec.md`
**Input**: Fix the rejection → re-implement review-feedback pipeline so a reviewer's rejection feedback survives from the rejection edge to the implementer's regenerated fix-mode prompt (issues #4899 + #5024, epic #3044).

## Summary

Two independent defects break one loop. **Write side (#4899):** the `in_review → in_progress`
(re-implement) rejection edge is silently feedback-lossy because five rejection-family sites are each
keyed on `target_lane == Lane.PLANNED`, so the re-implement edge skips content-read, cycle-persist,
resolvable-pointer emission, the no-rationale refusal, and the emitted-event `review_result` selection
(`_mt_hop_review_result`, `tasks_move_task.py:2539`) — leaving no record, an empty feedback location, a
non-resolvable synthetic `review:<WP>` reference, and an approval-shaped emitted `review_result`. **Render side (#5024):** even when a
resolvable record exists, (a) a fix-mode prompt-generation failure falls through to a feedback-less
full prompt with only a `logger.warning` the implementer never sees, and (b) on a coordination
topology the render reads the event log from the wrong partition, so the feedback is never found.

**Approach.** Collapse the five scattered `== PLANNED` rejection-family sites behind ONE pure predicate
`is_review_rejection_edge(old_lane, target_lane)` so the coupling (C-003) is enforced by construction
(WP01). Make the render fall-through emit a visible operator warning and re-route the render event-log
read through the `STATUS_STATE` placement seam so coord and single-branch render identically; add the
missing `build_implement_prompt_lines` test (WP02). The synthetic-marker / resolvable-pointer grammar
(`review/cycle.py`) is reused unchanged (NFR-001).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, `spec_kitty_events` (event log + Lamport reducer, unchanged); `mission_runtime.placement_seam` (partition resolution)
**Storage**: append-only `status.events.jsonl` (event log, `STATUS_STATE`/COORD partition on coord topologies); committed review-cycle artifacts under `tasks/<wp_slug>/` (`WORK_PACKAGE_TASK` partition)
**Testing**: pytest; ATDD red-first per defect (`tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`, `tests/agent/test_workflow_review_cycle_pointer.py`, `tests/characterization/test_trio_pure_cores.py`); `make test-fast` baseline + blast-radius module dirs
**Target Platform**: CLI (Linux/macOS dev; Windows CI parity)
**Project Type**: single (Python package `src/specify_cli/`)
**Performance Goals**: N/A — behavioral correctness, no hot path
**Constraints**: complexity ceiling ≤15 (C901/S3776); reuse the existing feedback grammar unchanged (NFR-001); no arbiter-override regression (NFR-003); no version numbers in scope (C-004); disjoint file ownership across WPs
**Scale/Scope**: two coupled defects, two work packages, one new pure predicate, one render-path partition re-route, one new test; ~4 source files touched

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority / canonical sources**: PASS. The mission adds ONE predicate as the single
  source of truth for the rejection-edge decision and reuses the canonical feedback grammar
  (`review/cycle.py`) and the canonical placement seam (`mission_runtime.placement_seam`) rather than
  improvising. No new parallel path.
- **DDD + tiered rigour**: PASS. The predicate lives in the transition core (domain lane logic); the
  render change lives in the workflow adapter. No layer inversion.
- **ATDD-first / red-first discipline**: PASS. Each defect carries an issue-pinned red-first scenario
  (NFR-002); SC-004 coord half is confirmed independently red (see Decision `plan.architecture.coord-render-partition`).
- **Campsite cleaning / complexity gate**: PASS with plan — `tasks_move_task.py` is ~3670 lines near the
  ceiling; WP01 does tidy-first behavior-preserving helper extractions (see Campsite Note) before/with the
  seam change.
- **Terminology adherence**: PASS. "Mission" not "feature"; no `feature*` aliases introduced.

No violations → Complexity Tracking table left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/review-feedback-to-implementer-01M3GKZ8/
├── plan.md              # This file
├── research.md          # Phase 0 output — F4 finding, seam rationale, NFR-003 analysis
├── data-model.md        # Phase 1 output — rejection-edge / record / reference / fix-mode entities
├── contracts/           # Phase 1 output — frozen predicate + render signatures WP02 consumes
│   ├── is-review-rejection-edge.md
│   └── render-feedback-contract.md
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── tasks_transition_core.py     # WP01: is_review_rejection_edge() predicate (new, pure); gates 2,3,4
├── tasks_move_task.py           # WP01: gate 1 (content read) + persist-call gate; tidy-first extractions
├── tasks_verdict_persistence.py # WP01 (read-only reference oracle: persist_rejected_review_cycle_for_rollback)
├── workflow_executor.py         # WP02: fix-mode fall-through visible warning + STATUS_STATE re-route
└── workflow_cores.py            # WP02: resolve_review_feedback_context / has_prior_rejection read path

src/specify_cli/review/
└── cycle.py                     # FROZEN (NFR-001): synthetic-marker / resolvable-pointer grammar — DO NOT MODIFY

tests/
├── specify_cli/cli/commands/agent/test_tasks_move_task_seam.py   # WP01 red-first (SC-001/002/003-write)
├── characterization/test_trio_pure_cores.py                      # WP01 pure-predicate + parity
├── agent/test_workflow_review_cycle_pointer.py                   # WP02 render + coord red-first (SC-004/005)
└── agent/test_build_implement_prompt_lines.py (NEW)              # WP02 build_implement_prompt_lines coverage
```

**Structure Decision**: Single Python package. The write-side change is confined to the two transition
modules under `cli/commands/agent/`; the render-side change is confined to `workflow_executor.py` +
`workflow_cores.py`. `review/cycle.py` is a read-only frozen dependency. This split gives WP01 and WP02
disjoint file ownership (WP01 owns the two transition modules; WP02 owns the two workflow modules), with
`review/cycle.py` shared read-only.

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*

## Architecture: the coupled write-side seam (WP01, C-003, #4899)

### The five rejection-family sites, keyed on `== Lane.PLANNED` today (verified on `issue-4899-...` @ current lines)

Gates 1–4 are the write-side edge; **site 5 (`_mt_hop_review_result`) selects the EMITTED event's
`review_result`** and was missed by the original four-gate framing. Routing gates 1–4 alone persists the
record but leaves the emitted event carrying an approval-shaped `review_result`, so **SC-001
field-for-field VALUE parity is NOT provable from gates 1–4 alone** — all five must route through the
predicate for the C-003 coupling to hold.

| # | Gate | Site | Today | Effect on `in_review → in_progress` |
|---|------|------|-------|-------------------------------------|
| 1 | Feedback content read | `tasks_move_task.py:615` `_mt_resolve_feedback` `if st.target_lane == Lane.PLANNED:` | Reads file content only for →planned | Content never read → empty feedback location |
| 2 | Persist-call gate | `tasks_move_task.py:2334` `if decision.planned_rollback and st.resolved_feedback_source is not None:` — sole caller of `persist_rejected_review_cycle_for_rollback`; `planned_rollback` set `tasks_transition_core.py:829` (`req.target_lane == Lane.PLANNED`) | Persists cycle only for →planned | No review-cycle record written |
| 3 | `emit_review_ref` selection | `tasks_transition_core.py:296` `if target_lane == Lane.PLANNED and review_feedback_pointer:` | Real pointer only for →planned; else falls through to `review_result.reference` synthetic `review:<WP>` | Non-resolvable synthetic reference left behind |
| 4 | No-rationale refusal | `tasks_transition_core.py:596` `_guard_planned_rollback` `if req.target_lane != Lane.PLANNED: return None` | Refuses no-rationale only for →planned | No-rationale re-implement rejection silently accepted |
| 5 | Emitted-event `review_result` selection | `tasks_move_task.py:2539` `_mt_hop_review_result` `if target == Lane.PLANNED and rejected is not None:` — `st.rejected_review_result` set at `tasks_verdict_persistence.py:966` once gate 2 fires | Returns the rejection `review_result` only for →planned | Skipped on the re-implement edge → falls to the approval-shaped branch at `:2562` (`verdict=APPROVED`, `reference="auto-forward:<WP>"`), mismatching gate 3's resolvable `review-cycle://` pointer → trips `_check_review_result_consistency`; **SC-001 value parity unprovable from gates 1–4 alone** |

### The seam (Decision `plan.architecture.rejection-edge-seam`)

Introduce ONE pure predicate, co-located with lane logic in `tasks_transition_core.py`:

```python
def is_review_rejection_edge(old_lane: str, target_lane: str) -> bool:
    """A rejection edge that must durably record reviewer feedback.
    Union of (a) the existing any-source rollback to ``planned`` and
    (b) the re-implement edge ``in_review -> in_progress`` (#4899)."""
    old = resolve_lane_alias(old_lane)
    target = resolve_lane_alias(target_lane)
    return target == Lane.PLANNED or (old == Lane.IN_REVIEW and target == Lane.IN_PROGRESS)
```

- **Why a union, not a rename.** Gates 1 and 4 fire today for `* → planned` from ANY source (e.g.
  `in_progress → planned`, `approved → planned`), governed by `_planned_rollback_message`'s Arm A/Arm B
  logic. Narrowing them to the `in_review` family would REGRESS that guard. The union keeps every
  existing `→planned` behavior and ADDS the re-implement edge — the minimal blast radius.
- **Single source of truth.** All five sites call the predicate; the coupling C-003 demands is enforced by
  construction — a future edit cannot half-fix the edge because there is one decision, not four.
- **Flag generalization.** `Emit.planned_rollback` (`tasks_transition_core.py:829`) is set from the
  predicate and renamed `is_review_rejection`; its two consumers — the persist-call gate
  (`tasks_move_task.py:2334`) and the plan-rebuild trigger (`tasks_move_task.py:2371`) — then flip together.
  The rebuild trigger's redundant explicit clause `(st.old_lane == Lane.IN_REVIEW and st.target_lane in
  (Lane.PLANNED, Lane.IN_PROGRESS))` is subsumed by the flag and removed (tidy-first).
- **Pointer flow.** On the re-implement edge the persist call (gate 2) now runs and sets
  `st.review_feedback_pointer`; the plan is rebuilt (`:2395`) with `review_feedback_pointer=st.review_feedback_pointer`,
  and gate 3's predicate is now true so the real `review-cycle://…` pointer is emitted instead of the
  synthetic token — matching the →planned edge field-for-field (FR-003).

### NFR-003 — arbiter-override moment must NOT regress

The arbiter-override forward edge is `in_review → {approved, done}` (detected `is_arbiter_override`,
`tasks_move_task.py:1146`; `arb_review_ref` threaded at `tasks_transition_core.py:300-303`;
`decision.arbiter_forward` rebuild trigger at `:2371`). It is OUTSIDE the predicate
(`target ∉ {planned, in_progress}`), so `is_review_rejection_edge` returns `False` for it and every
arbiter path is untouched by construction. WP01 keeps the existing arbiter-override coverage green as a
non-regression guard.

### Campsite Note — complexity ceiling (`tasks_move_task.py` ≈3670 lines)

The write-side change lands in a module near the C901/S3776 ≤15 ceiling. WP01 does behavior-preserving,
tidy-first extractions BEFORE the seam change so no touched function crosses 16:

- Extract the pointer-restore-and-persist block (`:2334-2348`, the `st.agent` save/restore around
  `persist_rejected_review_cycle_for_rollback`) into a named helper
  `_mt_persist_rejection_cycle(st, ports)` — isolates the persist-call gate behind the predicate and keeps
  `_mt_finalize_plan` under the ceiling.
- Keep the predicate itself pure and ≤3 lines (trivially under ceiling) so gates 2/3/4 shrink to a single
  call each rather than growing an `or` clause.
- Each extracted helper gets a focused unit test in the same WP (Sonar new-code coverage).

## Architecture: the render-guard change (WP02, #5024)

1. **Visible warning on fall-through** (`workflow_executor.py:1161-1163`). Today the `except` emits only
   `logger.warning(...)` then `return None`, silently degrading to a feedback-less full prompt (FR-006 bar:
   the warning must be *visible on the surface the implementer reads*, not log-only). Change: emit a
   `console.print("[bold red]⚠️ …[/bold red]")` (the surface the implementer reads) naming the WP and the
   failure, then `return None`. The block keeps concrete recovery logic (a bare log-only `except` is a
   Sonar finding); it does not silently substitute.
2. **`build_implement_prompt_lines` test** (`workflow_executor.py:1302`, currently untested). Add
   `tests/agent/test_build_implement_prompt_lines.py` exercising the feedback-present and feedback-absent
   branches directly (SC-003 positive control + the render assertion for SC-005).
3. **Render event-log partition re-route** (F4 resolution, `plan.architecture.coord-render-partition`).
   `implement_resolve_feedback_and_gate` (`workflow_executor.py:667`) resolves `feature_dir` via
   `read_dir(WORK_PACKAGE_TASK)` (PRIMARY partition) and reads the event log through it, but
   `status.events.jsonl` is a `STATUS_STATE` kind (COORD partition on coord topologies). Re-route the
   event-log read used by `resolve_review_feedback_context` / `latest_review_feedback_reference` /
   `has_prior_rejection` through `placement_seam(...).read_dir(STATUS_STATE)` (mirroring the write-side
   `_resolve_verdict_read_feature_dir`), while keeping the review-cycle-artifact read on
   `WORK_PACKAGE_TASK` (its correct partition). This is what makes SC-004/FR-007 pass on both topologies.

## F4 finding (SC-004 coord red-first caveat) — RESOLVED: INDEPENDENT-RED

The coordination-topology render defect is **independent** of the write-side loss, not a downstream
consequence. Given a durable, resolvable feedback record already present (write side fixed, event on the
COORD partition where the write side puts it), the render still fails on a coord topology because the
event-log read is mis-partitioned: `feature_dir` comes from `read_dir(WORK_PACKAGE_TASK)` (PRIMARY,
`artifacts.py:166`) while `status.events.jsonl` is `STATUS_STATE` (COORD, `artifacts.py:198,250-251`). On a
coord/lanes-with-coord topology those are different directories, so the render reads an empty event stream
and finds no resolvable `review_ref`.

**Consequence for the plan:** SC-004's coord half STAYS a valid red-first defect scenario (it is NOT
reclassified to a parity/non-regression assertion). WP02's scope expands to include the render-path
`STATUS_STATE` re-route (item 3 above). The implementer must still PROVE the coord half red-first on a real
coordination fixture with a record already present; if — contrary to this analysis — that fixture comes
back green, reclassify the coord half to parity then. **No spec SC-004 wording change is required** — the
caveat explicitly delegated this to plan, and the resolution takes the caveat's primary (independently
broken) branch.

## Work Package shape (confirmation for /spec-kitty.tasks)

> Implementation concerns below inform decomposition; `/spec-kitty.tasks` owns the final WP cut.

- **WP01 — write-side coupled change** (#4899, C-003). Owns `tasks_transition_core.py` + `tasks_move_task.py`.
  Adds `is_review_rejection_edge`; routes all five rejection-family sites (incl. `_mt_hop_review_result` at `tasks_move_task.py:2539`) + the no-rationale refusal through it; generalizes
  `Emit.planned_rollback → is_review_rejection`; conditional #3451 counter fix (see FR-008); tidy-first
  extractions. Reads `tasks_verdict_persistence.py` and `review/cycle.py` (frozen) as oracles.
- **WP02 — render guard + dual-topology render** (#5024, FR-005/006/007). Owns `workflow_executor.py` +
  `workflow_cores.py`. Visible fall-through warning; `STATUS_STATE` render re-route; new
  `build_implement_prompt_lines` test.
- **Dependency**: WP01 → WP02. SC-005 (end-to-end, no pre-seeding) requires the write side to produce a
  resolvable record before the render can surface it.
- **Disjoint file ownership**: WP01's two transition modules vs WP02's two workflow modules do not overlap;
  `review/cycle.py` is shared read-only (frozen). No shared-file contention on merge.
- **Contract-freeze (WP02 consumes from WP01/grammar)**: the `is_review_rejection_edge(old_lane, target_lane)
  -> bool` signature and the emitted resolvable-pointer shape (`review-cycle://…` via
  `st.review_feedback_pointer`), plus the frozen grammar predicates `is_non_resolvable_review_ref` /
  `is_synthetic_review_ref` and `ReviewCycleArtifact` — frozen in `contracts/`.

## Implementation Concern Map

### IC-01 — Coupled rejection-edge write seam

- **Purpose**: Make the `in_review → in_progress` rejection edge record feedback identically to `→planned`, with the coupling enforced by one predicate so it cannot be half-fixed.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-008 (conditional); C-003; NFR-003
- **Affected surfaces**: `tasks_transition_core.py` (predicate, gates 2/3/4, `Emit` flag), `tasks_move_task.py` (gate 1, persist-call gate, tidy-first extraction)
- **Sequencing/depends-on**: none (foundation)
- **Risks**: regressing the any-source `→planned` guard (mitigated by the union); regressing arbiter-override (out of predicate by construction, guarded by NFR-003 tests); complexity ceiling (mitigated by tidy-first extraction)

### IC-02 — Render surfacing + dual-topology parity

- **Purpose**: Ensure a durably recorded feedback record renders into the regenerated fix-mode prompt on both topologies, and that a generation failure is visible rather than silent.
- **Relevant requirements**: FR-005, FR-006, FR-007; NFR-002; SC-003, SC-004, SC-005
- **Affected surfaces**: `workflow_executor.py` (fall-through warning, `STATUS_STATE` re-route, `build_implement_prompt_lines` test), `workflow_cores.py` (feedback-context read path)
- **Sequencing/depends-on**: IC-01 (needs a resolvable record to render for the end-to-end SC-005 flow)
- **Risks**: the `STATUS_STATE` re-route must not break single-branch (single-branch collapses both partitions to `repo_root`, so the seam is a no-op there); artifact-dir read must stay on `WORK_PACKAGE_TASK`
