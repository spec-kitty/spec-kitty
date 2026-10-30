---
description: "Work package task list for agent-action-lane-context-refresh-01M66FF3"
---

# Work Packages: agent action implement refreshes a reused lane's workspace context

**Inputs**: Design documents from `kitty-specs/agent-action-lane-context-refresh-01M66FF3/`
**Prerequisites**: plan.md (required), spec.md, research.md

**Tests**: This mission is a defect fix; the red-first regression test IS the deliverable's proof (FR-002).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).

**Prompt Files**: Each work package references a matching prompt file in `kitty-specs/agent-action-lane-context-refresh-01M66FF3/tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`

---

## Work Package WP01: Red-first fix on the third claim path (Priority: P1) 🎯 MVP

**Goal**: `agent action implement`'s exists-path refreshes a reused lane's persisted workspace context to the newly claimed WP through the shared `refresh_reused_lane_context` helper, proven red-first by a regression test that claims two WPs into one lane and asserts no `ACTIVE_WP_CONTEXT_STALE` warning.
**Independent Test**: `uv run --frozen pytest tests/agent/test_agent_action_lane_context_refresh.py -q` is RED on the planning base branch and GREEN after the fix; the existing refresh tests (`tests/specify_cli/lanes/test_lane_context_refresh.py`, `tests/agent/test_orchestrator_lane_context_refresh.py`) stay green.
**Prompt**: `kitty-specs/agent-action-lane-context-refresh-01M66FF3/tasks/WP01-exists-path-context-refresh.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-002, C-003

### Included Subtasks

T001 Write the red regression test `tests/agent/test_agent_action_lane_context_refresh.py` (claim two WPs into one lane via `agent action implement`; assert context follows WP02 and no stale warning); witness RED on the base; commit the test as its own commit before any fix
T002 Route the exists-path onto the shared helper: call `refresh_reused_lane_context` from the `_reenter_self_heal` closure in `src/specify_cli/cli/commands/agent/workflow.py`; run the regression test to green
T003 Update the `refresh_reused_lane_context` docstring in `src/specify_cli/lanes/implement_support.py` (it names "both WP writers that reuse a lane"; now every claim path routes through it) and the reuse-arm comment that says the same
T004 Run the targeted blast-radius tests (new test + the existing refresh/self-heal test files + ruff/mypy/format on touched files) and record commands and counts

### Implementation Notes

- Red-first is binding (ATDD-First Discipline, DIRECTIVE_034): T001's test must be committed BEFORE T002's fix, and its RED run recorded.
- The fix is ~5 lines: one import + one call inside `_reenter_self_heal`, mirroring the arguments the orchestrator path passes (`src/specify_cli/orchestrator_api/wp_lifecycle.py:577-586`).
- Do NOT route the exists-path through `top_level_implement` (C-001, pinned by `tests/specify_cli/cli/commands/agent/test_implement_single_resolution.py:222`).

### Parallel Opportunities

- None — T001 → T002 → T003 are strictly ordered; T004 follows.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Mission-handle mismatch for the context filename → pass the same resolved `mission_slug` the command already threads to `top_level_implement`.
- Single-branch/repo-root lanes → the helper no-ops without a persisted lane context; the test fixture must use a real coordination-topology lanes mission.

---

## Work Package WP02: Changelog entry (Priority: P2)

**Goal**: An `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` documents the user-facing fix (bold impact-first lead with `(#6650)`, before/after, under 1,200 characters).
**Independent Test**: The entry exists, follows the changelog discipline (bold impact-first lead, `(#6650)` reference, before/after), and `git diff` shows no other changelog changes.
**Prompt**: `kitty-specs/agent-action-lane-context-refresh-01M66FF3/tasks/WP02-changelog-entry.md`
**Requirement Refs**: FR-001, C-003

### Included Subtasks

T005 Add the `[Unreleased]` changelog entry to `docs/changelog/CHANGELOG.md` describing the removed `ACTIVE_WP_CONTEXT_STALE` false warning on `agent action implement` lane reuse

### Implementation Notes

- User-facing change: operators running the shipped `spec-kitty-implement-review` skill see the warning on every lane commit after the first WP; after the fix they do not.
- Keep Mission vocabulary; no version numbers in scope.

### Parallel Opportunities

- None (single subtask).

### Dependencies

- Depends on WP01 (the entry describes the shipped fix).

### Risks & Mitigations

- Changelog drift → write it after WP01's final shape, citing the observed before/after.

---

## Dependency & Execution Summary

- **Sequence**: WP01 → WP02.
- **Parallelization**: None (strictly sequential, single-seam fix).
- **MVP Scope**: WP01 alone restores the behaviour; WP02 completes the user-facing record.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01, WP02 |
| FR-002 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01, WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red regression test for `agent action implement` lane reuse | WP01 | P1 | No |
| T002 | Refresh call on the exists-path seam | WP01 | P1 | No |
| T003 | Docstring/comment update on the shared helper | WP01 | P1 | No |
| T004 | Targeted blast-radius test run | WP01 | P1 | No |
| T005 | Changelog entry | WP02 | P2 | No |
