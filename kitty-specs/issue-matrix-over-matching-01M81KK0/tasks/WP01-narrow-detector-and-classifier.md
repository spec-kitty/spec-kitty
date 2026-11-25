---
work_package_id: WP01
title: Narrow the issue-matrix detector and classifier
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
planning_base_branch: issue-7808-issue-matrix-over-matching
merge_target_branch: issue-7808-issue-matrix-over-matching
branch_strategy: Planning artifacts for this mission were generated on issue-7808-issue-matrix-over-matching. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7808-issue-matrix-over-matching unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Implementation
history:
- at: '2026-11-22T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/tasks/
create_intent:
- tests/tasks/test_issue_matrix_over_matching.py
execution_mode: code_change
owned_files:
- src/specify_cli/tasks/issue_matrix.py
- src/specify_cli/tasks/issue_reference_discovery.py
- docs/adr/3.x/2026-09-20-1-issue-matrix-not-applicable-verdict.md
- tests/specify_cli/tasks/test_issue_reference_discovery.py
- tests/specify_cli/tasks/test_issue_reference_terminators.py
- tests/tasks/test_issue_reference_classification.py
- tests/tasks/test_issue_matrix_source_issue_7011.py
- tests/tasks/test_issue_matrix_citation_label_scope_7011.py
- tests/tasks/test_issue_matrix_over_matching.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 - Narrow the issue-matrix detector and classifier

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before resubmitting.

## Objective

Fix #7808, #5297 and #5516 in one change to the two owned modules: colour values are not issue
references, a commit-SHA citation is non-gating, and only `spec.md`, `tasks/` and closing keywords
gate. Keep one number-recognition authority (`_GH_ISSUE_PATTERN` + `_matched_issue_number`) and one
classifier (`classify_occurrence`). See plan.md D1-D5 and data-model.md for the exact rules.

## Branch Strategy

- Planning/base branch: `issue-7808-issue-matrix-over-matching`
- Final merge target: `issue-7808-issue-matrix-over-matching`
- The execution workspace is resolved by `spec-kitty agent action implement WP01 --agent claude --mission issue-matrix-over-matching-01M81KK0`; do not reconstruct its path.

## Subtasks

### T001 - Red-first acceptance tests

New file `tests/tasks/test_issue_matrix_over_matching.py`, through `discover_issue_references` /
`detect_issue_references` / `classify_occurrence`:
- research.md all-zero and all-digit colours (`color: #<6 digits>;`) give no reference;
- spec.md ``(`<sha>`, #N)`` gives a non-gating reference;
- research.md "Break #N" gives a cited (context-only) reference;
- spec.md "Closes #N" gives a gating reference;
- positive controls: a bare `#N` in spec.md and in tasks/ still gates; a real reference on a CSS line is kept.
Run them red before T002.

### T002 - Number filter (D1)

Leading-zero rejection in both arms of `_GH_ISSUE_PATTERN`; CSS declaration form check in
`_matched_issue_number`.

### T003 - Converge the patterns (D2)

`_CLOSING_KEYWORD_PATTERN` and `_SOURCE_DESCRIPTION_LEAD_PATTERN` keep only their labels; numbers
come from the canonical detector.

### T004 - Commit-citation rule (D3)

Positional backticked-SHA rule in `classify_occurrence`.

### T005 - Scope rule (D4)

`Occurrence.in_gating_scope` (default `True`); `discover_issue_references` sets `False` for
plan.md, research.md, analysis-report.md and contracts/; closing keyword first in the classifier.

### T006 - Re-pins and ADR

Re-pin any test that pinned the old over-matching, naming the ruling. Add "Amendment 2026-11-22"
to ADR 2026-09-20-1.

## Definition of Done

- T001 tests were red before the change and are green after it; completion recorded with `spec-kitty agent tasks mark-status`.
- Targeted suites green: `make test-fast`, the issue-reference/issue-matrix test families, `tests/policy/test_merge_gates_issue_matrix.py`, `tests/policy/test_issue_matrix_cross_site_consistency.py`, `tests/status/test_doctor.py`; out-of-matrix review tests run locally and disclosed.
- ruff, `ruff format --check --force-exclude`, mypy clean, no suppressions.

## Risks

- A fail-open path inside the gating scope: guard it with the positive-control tests.
- Out-of-map re-pins: record a one-line rationale per file.

## Reviewer Guidance

Check that no second number pattern or second gating predicate was introduced, and that every
demotion has a same-fixture positive control.
