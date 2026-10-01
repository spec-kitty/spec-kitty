# Tasks: Retrospect: one signal for documented review rejections

**Mission**: `retrospect-rejection-signal-01M3W27M` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Branch**: `claude/issue-2267-77kxtr` (planning base = merge target)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first #2267 repro through `generate_retrospective` over a documented-rejection event log | WP01 | |
| T002 | Create `specify_cli/review/rejection_signal.py` (feedback + backward-move + rejection predicates) with unit tests | WP01 | |
| T003 | Route the generator's rejection / lane-friction detectors through the predicate | WP01 | |
| T004 | Exclude documented rejections from the force-override detector | WP01 | |
| T005 | Count only undocumented `in_progress` re-entries in the implementation-cycle detector; update finding wording | WP01 | |
| T006 | Red-first repro for the hollow-review warning on documented-rejection force_count | WP02 | |
| T007 | Discount forced documented rejections from `force_count` in `_collect_force_count_warnings` | WP02 | |
| T008 | Non-vacuity: feedback-free forcing still warns; unreadable log keeps the raw count | WP02 | |
| T009 | CHANGELOG `[Unreleased]` entry | WP02 | |

## WP01 — Retrospective classifier reads one rejection predicate

**Goal**: FR-001..FR-004. A documented review rejection is reported once, as `review_loop`; undocumented forcing and re-entry still produce findings.
**Priority**: P1. **Dependencies**: none. **Estimated prompt size**: ~150 lines.

T001 Red-first #2267 repro through `generate_retrospective` (WP01)
T002 Create `specify_cli/review/rejection_signal.py` with unit tests (WP01)
T003 Route rejection / lane-friction detectors through the predicate (WP01)
T004 Exclude documented rejections from the force-override detector (WP01)
T005 Count only undocumented re-entries in the implementation-cycle detector (WP01)

## WP02 — Hollow-review warning reads the corrected signal

**Goal**: FR-005. Consolidate's hollow-review warning discounts forced documented rejections.
**Priority**: P2. **Dependencies**: WP01. **Estimated prompt size**: ~120 lines.

T006 Red-first repro for the hollow-review warning (WP02)
T007 Discount forced documented rejections in `_collect_force_count_warnings` (WP02)
T008 Non-vacuity controls (WP02)
T009 CHANGELOG entry (WP02)
