---
work_package_id: WP03
title: The done refusal names its cause
dependencies: []
requirement_refs:
- FR-005
- FR-006
- NFR-003
- SC-003
- SC-004
planning_base_branch: issue-6450-consolidate-run-gap-truthfulness
merge_target_branch: issue-6450-consolidate-run-gap-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6450-consolidate-run-gap-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6450-consolidate-run-gap-truthfulness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-run-gap-truthfulness-01M68ZR2
base_commit: 3f802bc1a04cbe1d4ea64217180072b3b75fce17
created_at: '2026-10-31T13:48:27.616365+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 2 - Message truthfulness
history:
- at: '2026-10-31T12:46:28Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/tasks/issue_matrix_approval.py
- tests/policy/test_merge_gates_issue_matrix.py
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – The done refusal names its cause

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Load the PM profile first: `spec-kitty agent profile show python-pedro`, then
`spec-kitty charter context --action implement`.

---

## Objectives & Success Criteria

Fix #6450 item (7): `issue_matrix_done_outcome`
(`src/specify_cli/tasks/issue_matrix_approval.py`) fails for two different families and renders one
message for both:

- rows **missing** or still `in-mission`/`unknown` (a verdict really is missing/unresolved), and
- a fully-verdicted matrix whose rows carry validation diagnostics (e.g. `deferred-with-followup`
  with `evidence_ref` "PR #1", which holds no follow-up handle).

Both currently get the header `"<artifact> has unresolved entries. Fill in verdicts before done."`
and the `_ISSUE_VERDICT_REMEDY` line telling the operator to run `spec-kitty agent issue-verdict`
per row — advice that is wrong for the second family, where every row already has a verdict.

Done when:

- A diagnostic-only failure (no missing rows, no in-mission rows) renders a message that names the
  artifact, keeps every diagnostic line verbatim, and contains neither `"Fill in verdicts"` nor the
  `agent issue-verdict` remedy.
- The missing-verdict/in-mission family keeps its exact existing wording, including
  `"has unresolved entries"`, `"Fill in verdicts before done."`, `"Still 'in-mission'"` and the
  remedy line.
- Both families still FAIL the terminality gate with the same blocking mode — no decision changes.

## Context & Constraints

Read first:

- `kitty-specs/consolidate-run-gap-truthfulness-01M68ZR2/spec.md` — FR-005, FR-006, SC-003, SC-004,
  NFR-003.
- `src/specify_cli/tasks/issue_matrix_approval.py` — `issue_matrix_done_outcome` (the message it
  builds), `_issue_matrix_present`, `_issue_matrix_evaluation`, `_issue_matrix_diagnostic_lines`,
  `_ISSUE_VERDICT_REMEDY`, `_missing_issue_matrix_message`.
- `src/specify_cli/policy/merge_gates.py::_evaluate_issue_matrix_verdict_terminality_gate` — the
  single consumer that turns the returned blocker into a FAIL gate result.
- `tests/policy/test_merge_gates_issue_matrix.py` — the real-git coord fixtures and the terminal
  positive control.
- `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` — the existing pins on the
  missing-verdict wording and on the deferred-without-handle diagnostics.

Constraints that matter:

- **FR-006 / C-002**: the decision never changes. Do not touch `_issue_matrix_evaluation`, the
  validator, or the gate's verdict/blocking computation. Only the header and whether the remedy line
  is appended may differ.
- `unknown` placeholders and `in-mission` rows must stay in the "verdict missing/unresolved" family:
  `unknown` is not a terminal verdict.
- **NFR-003**: the new message must not grow the refusal; it replaces the header and drops at most
  one remedy line.

## Branch Strategy

- **Strategy**: workspace-per-work-package on a lanes-topology Mission; the WP executes in its
  computed lane worktree and merges back into the mission target branch.
- **Planning base branch**: `issue-6450-consolidate-run-gap-truthfulness`
- **Merge target branch**: `issue-6450-consolidate-run-gap-truthfulness`

> Populated by `specify_cli`. Do not edit by hand.

## Subtasks & Detailed Guidance

### T008 — Red-first tests

In `tests/policy/test_merge_gates_issue_matrix.py` add a diagnostic-only case on the existing
`_build_coord_mission` fixture: every row verdicted, one row
`{"#1234": "deferred-with-followup"}` with `evidence_ref` "PR #1" (no `#NNN`/`Follow-up:` handle).
The matrix helper writes `evidence_ref: "PR #1"` for every row already, so a `deferred-with-followup`
verdict alone produces the diagnostic. Assert the terminality gate's `details`:

- does **not** contain `"Fill in verdicts"`;
- does **not** contain `"agent issue-verdict"`;
- still contains the diagnostic line (`"deferred-with-followup"` and the row id);
- `gate.verdict == GateVerdict.FAIL` and `gate.blocking is True` in block mode.

In `tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py` add the unit-level pair on
`_issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE)`: the diagnostic-only case above,
plus the missing-verdict control asserting the old wording still appears.

Record the failing output before the fix.

### T009 — Cause-dependent header and remedy

In `issue_matrix_done_outcome`, after `result.passed` / `missing_issues` / `unresolved_in_mission`
are known:

- `rows_need_verdicts = bool(missing_issues or unresolved_in_mission)`
- keep the current header when `rows_need_verdicts`;
- otherwise use a header that names the artifact and says the rows' verdicts are recorded but the
  matrix has validation errors (e.g. `f"{prefix} has validation errors; every referenced issue has a
  verdict recorded."`), and do not append `_ISSUE_VERDICT_REMEDY`.
- Keep the diagnostic lines, the `Missing rows:` line and the `Still 'in-mission'` line exactly as
  they are, in the same order.

### T010 — Prove no decision changed

Run, and paste the result into the WP completion note:

- `uv run pytest tests/policy/test_merge_gates_issue_matrix.py -q`
- `uv run pytest tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py -q`
- `uv run ruff check` / `uv run ruff format --check` on the touched files, plus `uv run mypy` on
  `src/specify_cli/tasks/issue_matrix_approval.py`.

## Test Strategy

Real-git gate fixture for the end-to-end message, helper-level tests for the exact strings. The
assertions are on the rendered refusal, not on internal branches.

## Definition of Done

- Red proof recorded, then green.
- The existing terminality and approval-blocker suites pass unchanged.
- No gate verdict or blocking mode differs anywhere.

## Risks

- Accidentally moving the `deferred-with-followup` family out of FAIL → the test asserts FAIL in the
  same fixture family as the positive control.
- Rewording the missing-verdict arm → the existing pins on `"has unresolved entries"` and
  `"Fill in verdicts before done."` fail loudly if so.

## Reviewer Guidance

Check that the only reachable change is the header text and the presence of the remedy line, that
`unknown`/`in-mission` rows still take the old path, and that the gate's verdict for every existing
fixture is unchanged.
