# Implementation Plan: Retrospect: one signal for documented review rejections

**Branch**: `claude/issue-2267-77kxtr` (planning base, target and landing branch; PR into `main`) | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/retrospect-rejection-signal-01M3W27M/spec.md`

## Summary

Move the "is this lane event a documented review rejection?" decision out of the retrospective generator into one review-owned module (`specify_cli/review/rejection_signal.py`), widen it to every backward rework move that carries review feedback, and make the four readers consume it: the generator's rejection, lane-friction, force-override and implementation-cycle detectors, and consolidate's hollow-review `force_count` check.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: none new; `specify_cli.status.verdict_vocab.is_changes_requested` (existing)
**Storage**: reads `status.events.jsonl` and `status.json` (no format change)
**Testing**: pytest; targeted files `tests/retrospective/test_generator.py`, `tests/specify_cli/retrospect/test_event_log_mining.py`, a new `tests/review/test_rejection_signal.py`, the consolidate hollow-review tests; plus `make test-fast`
**Target Platform**: CLI (Linux/macOS/Windows)
**Project Type**: single
**Performance Goals**: N/A (one extra linear pass over the event log at consolidate)
**Constraints**: no lane-matrix change (C-001), no record-schema change (C-002), complexity <= 15
**Scale/Scope**: 3 source modules (+1 new), ~5 test files

## Charter Check

- Single canonical authority: the predicate moves to `specify_cli/review/` (next to the review-ref sentinel vocabulary it must honour; `status` cannot import `review`) so the retrospective and consolidation packages read one definition instead of the generator owning a private copy that consolidate cannot see. PASS.
- Architectural alignment: `consolidation` and `retrospective` already import from `specify_cli.status`; no new edge. PASS.
- ATDD / red-first: each WP opens with an issue-pinned `@pytest.mark.regression` repro that is red on the base. PASS.
- Terminology: Mission / WP; "lane bounce" and "review loop" wording kept as-is in finding text except where it was wrong. PASS.
- No version numbers in scope. PASS.

## Design

```
review/rejection_signal.py          (new, canonical; reads review.cycle sentinels)
  has_documented_review_feedback(ev)   <- moved from generator._has_review_feedback
  BACKWARD_REWORK_MOVES                <- moved from generator._BACKWARD_LANE_MOVES (+ for_review/in_progress sources kept)
  is_backward_rework_move(ev)
  is_documented_review_rejection(ev) = is_backward_rework_move(ev) and has_documented_review_feedback(ev)

retrospective/generator.py
  _is_review_rejection_event  -> is_documented_review_rejection     (FR-002)
  _is_lane_friction_event      = backward and not rejection          (unchanged shape)
  _is_force_override_event     excludes documented rejections        (FR-003)
  _detect_implementation_cycles counts only re-entries with no documented
                                rejection since the previous entry   (FR-004)

consolidation/preflight.py
  _collect_force_count_warnings: effective = force_count
      - (forced documented-rejection events in status.events.jsonl)   (FR-005)
```

Decisions:

- **D-1 Rejection source lanes.** Any backward rework move carrying feedback is a rejection, including out of `for_review` and `in_progress`. The in-repo log has 45 `for_review → planned` and 83 `in_progress → planned` events carrying a `review-cycle://` ref; they are the reviewer's rejection issued without an `in_review` claim. Feedback-free backward moves stay lane friction (preserves #3687 and the existing `test_reviewer_feedback_transition_is_review_loop`).
- **D-2 Force-override count.** A forced documented rejection is counted only by the `review_loop` finding. Remaining force transitions keep the existing wording.
- **D-3 Implementation cycles.** The finding now reports *undocumented* re-entries; its summary/details say so. The first entry is never counted. A documented rejection licenses exactly one following re-entry.
- **D-4 Hollow-review.** Subtract forced documented rejections read from the event log; an unreadable log subtracts nothing (fail toward warning).
- **D-6 Sentinels are not feedback (post-tasks squad).** `force-override`, `action-review-claim`, legacy `workflow-review-claim` and synthetic `review:<WP>` refs are markers minted when no feedback artifact exists; they never make a move a rejection.
- **D-5 Out of scope.** Refusing `approved → in_progress` (issue comment, ask 2) changes the lane matrix (C-001); reported on the issue, not implemented.

## Project Structure

### Documentation (this mission)

```
kitty-specs/retrospect-rejection-signal-01M3W27M/
├── spec.md
├── plan.md
├── tasks.md
└── tasks/WP01-*.md, WP02-*.md
```

### Source Code (repository root)

```
src/specify_cli/review/rejection_signal.py        (new)
src/specify_cli/review/cycle.py                   (legacy `workflow-review-claim` sentinel)
src/specify_cli/retrospective/generator.py        (detectors)
src/specify_cli/consolidation/preflight.py        (hollow-review)
tests/review/test_rejection_signal.py              (new)
tests/retrospective/test_generator.py
tests/specify_cli/retrospect/test_event_log_mining.py
tests/consolidation/ (hollow-review collector tests)
docs/changelog/CHANGELOG.md
```

**Structure Decision**: single project, existing layout.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Canonical rejection predicate and retrospective detectors

- **Purpose**: Give the project one definition of a documented review rejection and make the retrospective detectors read it.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004
- **Affected surfaces**: `src/specify_cli/review/rejection_signal.py`, `src/specify_cli/review/cycle.py`, `src/specify_cli/retrospective/generator.py`
- **Sequencing/depends-on**: none
- **Risks**: the generator lazy-imports `specify_cli.status` to break an import cycle; the new module must be imported lazily there too.

### IC-02 — Hollow-review warning reads the corrected signal

- **Purpose**: Stop consolidate's hollow-review warning from counting documented rejections.
- **Relevant requirements**: FR-005
- **Affected surfaces**: `src/specify_cli/consolidation/preflight.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: `force_count` is computed by the external `spec_kitty_events` reducer; the subtraction must count the same events (forced, non-no-op) to stay consistent.
