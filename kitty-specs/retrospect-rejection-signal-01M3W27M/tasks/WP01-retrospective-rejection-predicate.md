---
work_package_id: WP01
title: Retrospective classifier reads one rejection predicate
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- SC-001
- SC-002
planning_base_branch: claude/issue-2267-77kxtr
merge_target_branch: claude/issue-2267-77kxtr
branch_strategy: Planning artifacts for this mission were generated on claude/issue-2267-77kxtr. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/issue-2267-77kxtr unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Classifier
history:
- at: '2026-10-01T15:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/retrospective/
create_intent:
- src/specify_cli/review/rejection_signal.py
- tests/review/test_rejection_signal.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/review/rejection_signal.py
- src/specify_cli/retrospective/generator.py
- src/specify_cli/review/cycle.py
- tests/review/test_rejection_signal.py
- tests/retrospective/test_generator.py
- tests/specify_cli/retrospect/test_event_log_mining.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Retrospective classifier reads one rejection predicate

## Load Agent Profile

Load `python-pedro` (implementer) before starting.

## Objectives & Success Criteria

- One review-owned predicate decides "documented review rejection" (FR-001).
- A backward rework move carrying review feedback out of `for_review`, `in_review`, `in_progress`, `approved` or `done` is a rejection (FR-002).
- `--force` findings exclude documented rejections (FR-003).
- Implementation-cycle findings count only re-entries with no documented rejection since the previous entry (FR-004).
- SC-001: the in-repo mission `worktree-owned-root-3328-01KZRG01` regenerates with no force / bounce / cycle noise for documented rework.

## Context & Constraints

- Spec: `kitty-specs/retrospect-rejection-signal-01M3W27M/spec.md`; plan decisions D-1..D-3.
- The generator lazy-imports `specify_cli.status` (import-cycle breaker); keep the new import lazy.
- Preserve #3687 behaviour: feedback-free rewinds out of `approved`/`done` stay lane friction; a WP with rework never lands in `helped`.
- No record-schema change (C-002), no lane-matrix change (C-001). Complexity <= 15.

## Subtasks

- **T001** Add a `@pytest.mark.regression` test pinned to #2267 in `tests/retrospective/test_generator.py` that writes a mission with documented rejections (out of `in_review` with `--force`, out of `for_review` with `--force`, out of `in_progress`) and asserts: one `review_loop` finding per WP, no force-override, no lane-bounce, no implementation-cycle finding. Must be RED on the base.
- **T002** Create `src/specify_cli/review/rejection_signal.py`: `has_documented_review_feedback`, `BACKWARD_REWORK_MOVES`, `is_backward_rework_move`, `is_documented_review_rejection`. Move the generator's `_has_review_feedback` / `_BACKWARD_LANE_MOVES` there (no duplicate left behind). Unit tests in `tests/review/test_rejection_signal.py`.
- **T003** `_is_review_rejection_event` / `_is_lane_friction_event` delegate to the predicate.
- **T004** `_is_force_override_event` returns False for documented rejections.
- **T005** `_detect_implementation_cycles` walks events in order and counts re-entries not licensed by a preceding documented rejection; update the finding text to say "re-entered in_progress N time(s) without a documented review rejection".

## Test surface

`tests/retrospective/test_generator.py`, `tests/specify_cli/retrospect/test_event_log_mining.py`, `tests/review/test_rejection_signal.py`, `tests/retrospective/`, `tests/specify_cli/retrospective/`, plus `make test-fast`. No heavy suites.

## Activity Log

- 2026-10-01T15:50:00Z – system – Prompt created.
