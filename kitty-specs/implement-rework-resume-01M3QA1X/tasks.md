# Work Packages: Implement resumes after in_review to in_progress rejection

**Inputs**: Design documents from `/kitty-specs/implement-rework-resume-01M3QA1X/`
**Prerequisites**: plan.md, spec.md, research.md

**Organization**: one work package; the change is a single concern (IC-01) across two `status/` modules and the move-task core that already consumes the projection.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Implementer of record resumes after a rework verdict (Priority: P1) 🎯 MVP

**Goal**: `agent action implement` admits the implementer of record on an `in_progress` WP after an `in_review → in_progress` rework verdict, without `--force`; third tools stay refused; a read failure fails closed.
**Independent Test**: `test_rework_unforced_loop.py::test_action_implement_resumes_after_in_progress_rejection` (RED on the planning base) plus the ratchet in `test_rework_guard_ratchets.py`.
**Prompt**: `tasks/WP01-implementer-resume.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, C-001, C-002, C-003, SC-001, SC-002

### Included Subtasks

- T001 Red-first: real-CLI regression through `agent action implement` (`tests/specify_cli/cli/commands/agent/test_rework_unforced_loop.py`) + third-tool ratchet (`test_rework_guard_ratchets.py`); commit before the fix.
- T002 Shared predicate `is_latest_implementer(latest, actor)` in `src/specify_cli/status/review_roles.py`; `tasks_transition_core._ownership_role_allowance` / `_implementer_arm` reuse it (behaviour-preserving).
- T003 `start_implementation_status` IN_PROGRESS arm admits the implementer of record via an extracted, fail-closed helper (function-local `review_roles` import; no extra read on the unchanged paths; `claimed_by` = the admitted requester).
- T004 Unit tests: predicate (`tests/unit/status/test_review_roles.py`) and lifecycle arm (`tests/status/test_work_package_lifecycle.py`: admit, third tool, generic, empty log, forced reject without `review_ref`, read failure); fail-closed real-CLI test; drop the `regression` marker.
- T005 CHANGELOG `[Unreleased]` entry and orchestrator-API `WP_ALREADY_CLAIMED` doc note.

### Dependencies

None.

### Risks & Mitigations

- Import cycle (`review_roles` imports the lifecycle module) → function-local import.
- Append-order projection vs Lamport reducer slot (#4941) → accepted residual, noted in the PR.

## Requirements Coverage Summary

| Requirement | WP |
|---|---|
| FR-001, FR-002, FR-003, FR-004 | WP01 |
| NFR-001, NFR-002 | WP01 |
| C-001, C-002, C-003 | WP01 |
| SC-001, SC-002 | WP01 |
