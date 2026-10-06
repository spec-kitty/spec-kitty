# Implementation Plan: Align the composition-backed run advance with the engine advance

**Branch**: `issue-2562-composition-advance-alignment` (stacked on #5834) | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/composition-advance-alignment-01M49EKF/spec.md`

## Summary

A composition-backed advance plans through a parallel adapter planner (`apply_result` + `plan_next`), so it skips the engine's audit-significance evaluation and its RACI recording. This plan routes the composition advance through the engine's single planning authority (`plan_advance`) and single commit path (`commit_advance`). The commit path is rebuilt from per-event primitives, and the adapter keeps only what is genuinely composition-specific:
- the FR-008 plan-first refusal;
- emitter seeding;
- a pre-completion retrospective guard;
- the post-completion non-blocking capture;
- the CLI `Decision` mapping.

`provide_decision_answer` is split by behaviour-preserving extraction to remove the last `# noqa: C901`.

The shape is the "recommended final shape" of the post-spec squad (research.md R-2).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pydantic (run snapshot, advance plan), `spec_kitty_events.mission_next` payloads (unchanged)
**Storage**: per-run `state.json` + `run.events.jsonl` under `.kittify/runtime/runs/<run_id>/`
**Testing**: pytest. Red-first acceptance through `decide_next_via_runtime` (twin-run parity against the engine `next_step`), engine unit tests, AST shape gates, characterisation tests for `provide_decision_answer`
**Target Platform**: the CLI (`spec-kitty next`)
**Project Type**: single project
**Performance Goals**: no extra I/O beyond one snapshot read for the stale check (the adapter already read the snapshot to seed)
**Constraints**: C-001..C-005 of the spec; complexity ≤ 15; mypy adds no errors over the 21 already on the base
**Scale/Scope**: `src/runtime/next/_internal_runtime/engine.py`, `src/runtime/next/runtime_bridge_engine.py`, `src/runtime/next/runtime_bridge.py` (`_dn_plan_composition_advance` only), their tests, CHANGELOG

## Charter Check

- **Single canonical authority**: met. One planner (`plan_advance`) and one commit path (`_commit_advance`) remain, and the adapter's parallel planner is deleted.
- **ATDD-first / red-first (SO #4, C-011)**: met. The four acceptance tests are already red on the base for the right reasons (recorded in traces/approach.md) and are committed before the change.
- **Architectural gate discipline (SO #5)**: met.
  - The shape gates added here (the adapter constructs no event payloads and defines no composition planner) start empty, with no allowlist.
  - Engine-private access stays concentrated in `runtime_bridge_engine` (`tests/runtime/test_bridge_engine.py`).
- **Campsite (SO #2)**: met. The tidy-first enabler is to characterise `provide_decision_answer`, then extract its helpers, as a distinct preceding behaviour-preserving work package.
- **Mission hygiene (SO #8)**: met. The issue matrix carries #2562, the opening comment is posted, and the reviewer is separate from the implementer.
- **No full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION)**: met. Only the targeted surface listed in quickstart.md is run.

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/composition-advance-alignment-01M49EKF/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── checklists/requirements.md
├── traces/ (approach.md, design-decisions.md, tooling-friction.md)
└── tasks.md + tasks/ (from /spec-kitty.tasks)
```

### Source Code (repository root)

```
src/runtime/next/
├── _internal_runtime/engine.py      # per-event primitives, _commit_advance(before_run_completed=…), provide_decision_answer split
├── runtime_bridge_engine.py         # adapter: commit via engine; composition planner + payload code deleted
└── runtime_bridge.py                # _dn_plan_composition_advance → _engine_adapter.plan_advance
tests/runtime/
├── test_composition_advance_alignment.py   # NEW acceptance (twin-run parity)
├── test_bridge_engine.py                   # re-seamed stubs + shape gates
└── test_bridge_decision_log_flush.py       # re-seamed stubs
tests/next/ (engine primitive + provide_decision_answer characterisation tests)
docs/changelog/CHANGELOG.md
```

**Structure Decision**: single project; changes stay in `src/runtime/next/` and its tests (C-001).

## Complexity Tracking

_None._

## Implementation Concern Map

### IC-01: Characterise and split `provide_decision_answer`

- **Purpose**: remove the last `# noqa: C901` in the engine without changing behaviour. This is the tidy-first enabler on the engine module the later concerns edit.
- **Relevant requirements**: FR-011, NFR-001
- **Affected surfaces**: `_internal_runtime/engine.py::provide_decision_answer`; `tests/next/` characterisation tests
- **Sequencing/depends-on**: none
- **Risks**: the medium-band "re-add pending" path reads `snapshot.pending_decisions` (the original), not the mutated copy. The denial event carries `rationale_linkage=None`. Both are pinned by characterisation first.

### IC-02: Engine per-event primitives and the pre-completion guard

- **Purpose**: one definition of each run-event recording (step completed, significance, step issued, decision input requested with dedupe, run completed), plus an optional `before_run_completed` guard on `_commit_advance` / `commit_advance` that can only abort.
- **Relevant requirements**: FR-005, FR-008 (seam), NFR-001
- **Affected surfaces**: `_internal_runtime/engine.py`; engine unit tests
- **Sequencing/depends-on**: IC-01 (same module; sequential to avoid churn)
- **Risks**: event order and the snapshot-write timing must stay byte-identical for `next_step` (pinned by the existing engine tests).

### IC-03: Route the composition advance through the engine (the behaviour change)

- **Purpose**: close the significance/RACI gap. The bridge plans with `plan_advance`. The adapter refuses as before, seeds, commits through `commit_advance` with the retrospective guard, runs the non-blocking capture after a terminal commit, and maps the decision. The adapter's planner, plan type and payload code are deleted.
- **Relevant requirements**: FR-001..FR-010, FR-012
- **Affected surfaces**: `runtime_bridge_engine.py`, `runtime_bridge.py::_dn_plan_composition_advance`, `tests/runtime/test_composition_advance_alignment.py`, the re-seamed adapter tests, CHANGELOG
- **Sequencing/depends-on**: IC-02
- **Risks**:
  - The adapter unit tests stub the old seam (squad BLOCKER). They are re-seamed with every assertion kept.
  - A `StaleAdvancePlan` must surface as the EDGE-003 blocked Decision, never as a legacy fall-back.
  - Dead symbols (`apply_result` wrapper, `_mark_step_completed`, `_live_template_path`) must be deleted, or the dead-symbol gate flags them.
