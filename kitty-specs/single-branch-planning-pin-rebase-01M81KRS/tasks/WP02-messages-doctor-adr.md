---
work_package_id: WP02
title: Messages, doctor and ADR
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-010
planning_base_branch: issue-7793-single-branch-planning-pin
merge_target_branch: issue-7793-single-branch-planning-pin
branch_strategy: Planning artifacts for this mission were generated on issue-7793-single-branch-planning-pin. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7793-single-branch-planning-pin unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: Phase 3 - Messages and governance
history:
- at: '2026-11-22T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/tasks_move_task.py
create_intent:
- docs/changelog/unreleased/7793-single-branch-planning-pin.fixed.md
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/migration/mission_state.py
- src/specify_cli/cli/commands/_mission_state_doctor.py
- tests/specify_cli/cli/commands/agent/test_single_branch_refusal_wording.py
- tests/integration/migration/test_doctor_rebuild_derived_pin_7210.py
- docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md
- docs/changelog/unreleased/7793-single-branch-planning-pin.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Messages, doctor and ADR

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completion and record progress with `spec-kitty agent tasks add-history <WPID> --note "..."`.

---

## Objectives & Success Criteria

- FR-007: the `SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE` and `SINGLE_BRANCH_IMPLEMENTATION_MISSING` texts in `_mt_require_single_branch_evidence` name the route that works: `finalize-tasks --refresh-planning-commit` (plus `--allow-orphaned` after a rebase). Codes unchanged.
- FR-010: a doctor rebuild whose pin stays `None` reports a new action `lanes_rebuilt_pin_unset` and prints a warning. Both pin warnings name the next step.
- The ADR amendment records the rules (pin branch line, patch-id follow, window guard, derived freeze, derivation anchor) and the residuals (research R5).

## Context & Constraints

- C-005: `tasks_move_task.py` overlaps #7809. Change message text only.
- The doctor change overlaps Slice 10. Keep it to the two warnings and one action constant.
- Writing doctrine: plain language, audience = operator.

## Branch Strategy

- **Strategy**: single_branch (settled by finalize-tasks from the WP count/lane count)
- **Planning base branch**: `kitty/mission-single-branch-planning-pin-rebase-01M81KRS`
- **Merge target branch**: `issue-7793-single-branch-planning-pin`
- Execution workspaces come from `lanes.json`; on single_branch the WP runs in the repository root checkout.

## Subtasks

### T010 Remedies
Update the two strings and their wording test (out-of-matrix: disclose).

### T011 Doctor
`_rebuilt_planning_commit` callers: `planning_commit_sha is None and not derived` adds `LANES_REBUILT_PIN_UNSET_ACTION`. `_mission_state_doctor.py` prints it with the next step; the tip warning gains it. Extend `test_doctor_rebuild_derived_pin_7210.py`.

### T012 ADR and changelog
`## Amendment 2026-11-22 (#7793, #7297)` in ADR `2026-10-04-5`; changelog fragment `7793-single-branch-planning-pin.fixed.md` per `docs/changelog/unreleased/README.md`.

## Test Strategy

The two test files above plus `make test-fast`.

## Definition of Done

Texts asserted by tests; ADR reviewed for plain language.

## Risks

Message tests in other suites asserting old remedy substrings: grep before editing.

## Reviewer Guidance

Every remedy named must work on the shape it is printed for.
