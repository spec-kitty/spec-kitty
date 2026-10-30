---
work_package_id: "WP03"
title: "Folded into WP01 and WP02 (canceled)"
task_type: "implement"
phase: "Phase 0 - Retired"
execution_mode: "code_change"
dependencies: []
requirement_refs: []
tracker_refs:
  - "#6632"
owned_files: []
create_intent: []
authoritative_surface: "src/specify_cli/review/"
agent_profile: "python-pedro"
role: "implementer"
agent: "claude"
model: ""
subtasks: []
planning_base_branch: "issue-6632-review-feedback-draft-retirement"
merge_target_branch: "issue-6632-review-feedback-draft-retirement"
branch_strategy: "Planning artifacts were generated on issue-6632-review-feedback-draft-retirement. Completed changes must merge back into issue-6632-review-feedback-draft-retirement."
assignee: ""
shell_pid: ""
history:
  - at: "2026-10-30T17:52:00Z"
    actor: "system"
    action: "Retired: the red-test package was folded into WP01 so one package lands the red commit and the fix together."
---

# Work Package Prompt: WP03 – Folded into WP01 and WP02 (canceled)

This work package was canceled before implementation started. A separate red-test-only package cannot
pass its own per-WP review while its tests are red, and the charter's ATDD-First Discipline prescribes
the red test as the first commit *of the lane*, not as its own package. Its content now lives in WP01
(the end-to-end regression is WP01's first commit) and WP02 (prompt wording, guide, changelog).

The file is kept so the Mission's status snapshot and its work-package files agree (#5579): the
`canceled` lane is recorded in the event log, and a snapshot entry without a file reads as a
disagreement to `tests/contract/test_mission_status_reality.py`.
