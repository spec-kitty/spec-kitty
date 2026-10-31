---
work_package_id: WP01
title: Red-first contract tests for the three lifecycle emitters
dependencies: []
requirement_refs:
- FR-004
- FR-005
planning_base_branch: issue-6438-build-lifecycle-payloads-from-models
merge_target_branch: issue-6438-build-lifecycle-payloads-from-models
branch_strategy: Planning artifacts for this mission were generated on issue-6438-build-lifecycle-payloads-from-models. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6438-build-lifecycle-payloads-from-models unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-6438-build-lifecycle-payloads-from-models-01M68ZPD
base_commit: d396d552f95ce7d2bc3cdb32ab15b3ed57b37bd7
created_at: '2026-10-31T12:46:35.305669+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Red
history:
- at: '2026-10-31T12:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/status/
create_intent:
- tests/specify_cli/status/test_model_built_payloads_6438.py
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/status/test_model_built_payloads_6438.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first contract tests for the three lifecycle emitters

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status` before starting. Address every feedback item with
`spec-kitty agent tasks add-history WP01 --note "..."`.

## Objectives & Success Criteria

Create `tests/specify_cli/status/test_model_built_payloads_6438.py` so that, for each of the three
emitters, both halves of the contract are pinned:

1. a successful emit persists exactly the canonical model's JSON dump;
2. an emit whose payload the model rejects raises before anything is appended.

The module must be **red on the pre-change emitters** (they accept and write the invalid payload) and
**green once WP02 lands**. A test that passes before the change proves nothing.

## Context & Constraints

- Issue #6438; spec `kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/spec.md` (FR-004, FR-005).
- Contract: `kitty-specs/issue-6438-build-lifecycle-payloads-from-models-01M68ZPD/contracts/lifecycle-payloads.md`.
- Source under test: `src/specify_cli/status/lifecycle_events.py` — `emit_mission_reopened`,
  `emit_follow_up_recorded`, `emit_reviewer_self_approval`.
- Model reference test: `tests/specify_cli/status/test_post_mission_lifecycle_events.py` for the
  "completed mission" fixture shape (`_write_meta` with `merged_at`).
- Only public emitters are called. No private helper, no monkeypatching of the write path.
- Do not edit `src/` in this WP. If a test cannot be written without changing the emitters, stop and report.

## Branch Strategy

- **Strategy**: feature-branch on `issue-6438-build-lifecycle-payloads-from-models`
- **Planning base branch**: `issue-6438-build-lifecycle-payloads-from-models`
- **Merge target branch**: `issue-6438-build-lifecycle-payloads-from-models`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not change manually.

## Subtasks & Detailed Guidance

### Subtask T001 – Module skeleton and the two shared fixtures

- **Purpose**: One fixture per emitter class so the positive and negative assertion of the same emitter
  cannot drift apart.
- **Steps**:
  - `pytestmark = pytest.mark.fast`.
  - `_completed_mission(tmp_path)` → feature dir with `meta.json` carrying `created_at`,
    `merged_at`, `mission_id` (`01ARZ3NDEKTSV4RRFFQ69G5FAV`), `mission_number`, `mission_slug`,
    `target_branch`. `merged_at` is what makes `is_mission_completed` true.
  - `_wp_dir(tmp_path)` → any feature dir; `emit_reviewer_self_approval` has no completion guard.
  - `_line_count(feature_dir)` helper reading `mission_event_log_path(feature_dir)`.
- **Files**: `tests/specify_cli/status/test_model_built_payloads_6438.py`
- **Parallel?**: no (everything else builds on it).
- **Notes**: use `tmp_path`; never write into the repository tree.

### Subtask T002 – `MissionReopened`

- **Purpose**: Pin the model conformance and the refusal of a contract-invalid `reason`.
- **Steps**:
  - Positive: call `emit_mission_reopened(...)` with a real reason; assert the returned envelope's
    `payload` equals `MissionReopenedPayload(**payload).model_dump(mode="json", exclude_none=False)`
    and that `cleared_merge` is present and `None`; assert the log grew by one line.
  - Negative: call again with `reason=""`; `pytest.raises(ValidationError)`; assert the line count is
    unchanged.
- **Files**: same module.
- **Parallel?**: yes (disjoint functions).
- **Notes**: `reason=None` is also worth one assertion — the 10.7.0+ schema rejects it and the emitter
  types `reason: str`.

### Subtask T003 – `FollowUpRecorded`

- **Purpose**: The same pair for both discriminators.
- **Steps**:
  - Positive `commit`: `follow_up_type="commit"`, `commit_sha="a"*40`; payload equals
    `FollowUpRecordedPayload(**payload).model_dump(mode="json", exclude_none=False)`; `pr_number` is `None`.
  - Positive `pr`: `follow_up_type="pr"`, `pr_number=1234`; `commit_sha` is `None`.
  - Negative: `recorded_by=""` → `ValidationError`, log unchanged.
- **Files**: same module.
- **Parallel?**: yes.
- **Notes**: do **not** use a missing `pr_number` as the negative case — the emitter's own guard already
  rejects it, which would make the test green before the change.

### Subtask T004 – `ReviewerSelfApproval`

- **Purpose**: The same pair for the WP-level fallback approval.
- **Steps**:
  - Positive: payload equals
    `ReviewerSelfApprovalPayload(**payload).model_dump(mode="json", exclude_none=False)`; log grew by one.
  - Negative: `failure_reason=""` → `ValidationError`, log unchanged.
- **Files**: same module.
- **Parallel?**: yes.
- **Notes**: the emitter has no completion guard, so no `meta.json` is required for this one.

### Subtask T005 – Prove the module is red on the pre-change code

- **Purpose**: The red-first evidence the mission depends on.
- **Steps**:
  - `git stash` the new module? No — instead run it against the untouched emitters **before** WP02 starts:
    `uv run pytest tests/specify_cli/status/test_model_built_payloads_6438.py -q` and confirm the three
    negative cases fail (`DID NOT RAISE`), while the positive assertions pass.
  - Record the observed failure text in `spec-kitty agent tasks add-history WP01 --note "..."`.
- **Files**: none.
- **Parallel?**: no.
- **Notes**: if the negative cases do not fail, the test is vacuous — fix the chosen field.

## Test Strategy

```bash
uv run pytest tests/specify_cli/status/test_model_built_payloads_6438.py -q
```

- Both the positive and negative assertion for one emitter must use the **same** fixture, so "nothing
  was written" is proven against a log that provably can receive a line.
- Typecheck the new module the way CI does: `uv run mypy tests/specify_cli/status/test_model_built_payloads_6438.py`
  (add `# type: ignore[...]` only where the existing suites already need it).

## Risks & Mitigations

- Vacuous negative case → pick a field only the pydantic model constrains.
- Fixture drift from the existing post-mission suite → copy the `meta.json` shape from
  `test_post_mission_lifecycle_events.py::_write_meta`, do not invent one.

## Review Guidance

- Are all three emitters covered in both directions, on one shared fixture each?
- Does any assertion pass on the pre-change code? If yes, it is not evidence.
- Is any pre-existing test edited? It must not be.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
