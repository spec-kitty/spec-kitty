---
work_package_id: WP02
title: Hollow-review warning reads the corrected signal
dependencies:
- WP01
requirement_refs:
- FR-005
planning_base_branch: claude/issue-2267-77kxtr
merge_target_branch: claude/issue-2267-77kxtr
branch_strategy: Planning artifacts for this mission were generated on claude/issue-2267-77kxtr. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/issue-2267-77kxtr unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Consolidate
history:
- at: '2026-10-01T15:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/preflight.py
- tests/consolidation/test_hollow_review_warnings.py
- docs/changelog/CHANGELOG.md
- src/specify_cli/review/rejection_signal.py
- tests/review/test_rejection_signal.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Hollow-review warning reads the corrected signal

## Load Agent Profile

Load `python-pedro` (implementer) before starting.

## Objectives & Success Criteria

- FR-005: `_collect_force_count_warnings` discounts forced documented review rejections (read from `status.events.jsonl` via `specify_cli.status.review_rejection`) from `status.json`'s `force_count` before applying the `>= 2` threshold.
- Feedback-free forcing still warns (non-vacuity); an unreadable or absent event log keeps the raw count (fail toward warning).

## Context & Constraints

- Plan decision D-4. `force_count` is computed by the `spec_kitty_events` reducer from forced transitions; count the same shape (forced, `from_lane != to_lane`).
- Keep the existing warning text `force_count=<n>`, reporting the effective count.
- Complexity <= 15; extract a helper if needed, with direct tests.

## Subtasks

- **T006** `@pytest.mark.regression` test pinned to #2267 in `tests/consolidation/test_hollow_review_warnings.py`: `force_count=2`, both forced events are documented rejections, implementer == approver → no warning. RED on the base.
- **T007** Implement the discount.
- **T008** Controls: feedback-free forced events still warn; missing/unreadable log keeps raw count.
- **T009** `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` covering WP01 + WP02 (bold impact-first lead, `(#2267)`, before → after).

## Test surface

`tests/consolidation/test_hollow_review_warnings.py`, `tests/consolidation/test_preflight_seam.py`, plus `make test-fast`. No heavy suites.

## Activity Log

- 2026-10-01T15:50:00Z – system – Prompt created.
