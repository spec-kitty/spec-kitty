---
description: "Work package task list for the Next dependency wedge mission"
---

# Work Packages: Next dependency wedge — dispatch the review

**Inputs**: Design documents from `/kitty-specs/next-dependency-review-dispatch-01M46TJ7/`
**Prerequisites**: plan.md (required), spec.md (user stories), research/code-grounding.md

**Tests**: Red-first ATDD is mandatory for every work package (ADR 2026-07-17-1, C-003) — an issue-pinned `@pytest.mark.regression` reproduction RED on the merge-base through the pre-existing entry point, GREEN after the fix.

**Organization**: Two independently-deliverable work packages. WP01 and #5310 both edit `src/runtime/next/runtime_bridge.py`, so they are one WP (the no-`owned_files`-overlap guard forbids splitting the same file across WPs); each defect still lands red-first in its own commit. WP02 is an independent file.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`.

---

## Work Package WP01: Finalized-board routing — the wedge + advance first-contact parity (Priority: P1) 🎯

**Goal**: `next` (dispatch **and** query) dispatches the review of a `for_review` WP when the only `planned` work is dependency-walled, and advance on first contact honours the finalized board instead of booting a fresh discovery run.
**Independent Test**: On a 2-WP board (`WP02` deps `WP01`, WP01 `for_review`, WP02 `planned`), `next --result success` and `next` query both resolve a `review` step for WP01; and with no persisted run on a finalized board, advance agrees with query.
**Prompt**: `/tasks/WP01-finalized-board-routing.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Red-first (Defect 1, #5669): routing unit + dispatch + query all assert `review` (RED on merge-base) in `tests/next/test_next_dependency_wedge_5669.py`
T002 Fix: gate the `planned` arm of `_finalized_task_board_override_step` on `preview_claimable_wp`; keep `claimed`/`in_progress` resume arms; reach `for_review`→`review`
T003 Red-first (#5310): advance first-contact vs query parity on a finalized board (RED) in `tests/next/test_next_advance_first_contact_5310.py`
T004 Fix: make advance first-contact consult the finalized-board authority (agree with query), inheriting T002's corrected verdict
T005 Verify `orchestrator_api/decision_verbs.py` shares the next/board seam (no parallel override); add/extend coverage if a gap is found

### Implementation Notes

- One routing authority: reuse `discovery.py::preview_claimable_wp`; do not mint a second claimability predicate (C-001).
- Preserve the #4860 guard (FR-002) and the `done`/`accept`/`review_in_progress`/`no_actionable_wp` endings byte-identical (NFR-002); no `decision.py` change (its fallback is live but preempted — assert that).

### Parallel Opportunities

- T001/T003 (independent test files) can be written in parallel; T002 precedes T004 (T004 builds on the corrected override).

### Dependencies

- None (foundational). Internal order: T001→T002, T003→T004 (T004 after T002).

### Risks & Mitigations

- Making the override dependency-aware must not deepen the pre-existing claimed/in_progress-only blocked floor; gate ONLY the planned arm. Confirm the query call-site threads coord-aware dirs.

---

## Work Package WP02: Scoped dirty-gate survivor for `mission-events.jsonl` (Priority: P1)

**Goal**: `next`'s uncommitted `kitty-specs/<slug>/mission-events.jsonl` no longer refuses a `move-task` transition (`for_review`/`approved`/`done`), while an operator-owned dirty file still blocks and the global churn owner is untouched.
**Independent Test**: With only `mission-events.jsonl` dirty, `move-task <wp> --to approved` is not refused; with an operator file also dirty, it still blocks.
**Prompt**: `/tasks/WP02-mission-events-dirty-survivor.md`
**Requirement Refs**: FR-006, FR-007, C-002, SC-004

### Included Subtasks

T006 Red-first (#5669 part 2): the move-task dirty gate refuses over `mission-events.jsonl` (RED) + operator-file negative control, in `tests/review/test_mission_events_dirty_survivor_5669.py`
T007 Fix: add `kitty-specs/<slug>/mission-events.jsonl` (exact-anchored, function-local literal) to `_is_review_handoff_survivor_path`
T008 Assert the global churn owner (`is_self_bookkeeping_churn`/`is_toolchain_generated_churn`) is UNCHANGED for `mission-events.jsonl` (C-002 guard)

### Implementation Notes

- Scoped to the review/move-task gate only. Do NOT widen the global owner (destructive consolidate/accept/merge consumers + research-gate readers). Mirror the file's function-local-literal pattern (R-014 exemption-registry scan).

### Parallel Opportunities

- Fully independent of WP01 (different module).

### Dependencies

- None.

### Risks & Mitigations

- Anchor the match to `kitty-specs/<slug>/mission-events.jsonl` so a user file named `mission-events.jsonl` elsewhere still blocks (FR-007 negative control).

---

## Dependency & Execution Summary

- **Sequence**: WP01 and WP02 are independent; either order. (Driven via explicit implement/review verbs, not the `next` loop, to avoid dogfooding the wedge.)
- **MVP Scope**: Both WPs are P1 release-blocker scope.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP01 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP02 |
| C-003 | WP01, WP02 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |
| SC-004 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first Defect 1 (wedge) | WP01 | P1 | Yes |
| T002 | Fix override planned-arm gate | WP01 | P1 | No |
| T003 | Red-first #5310 (advance first-contact) | WP01 | P1 | Yes |
| T004 | Fix advance first-contact board consult | WP01 | P1 | No |
| T005 | Verify orchestrator-api shares the seam | WP01 | P1 | No |
| T006 | Red-first Defect 2 (dirty-gate refusal) | WP02 | P1 | Yes |
| T007 | Add anchored mission-events survivor | WP02 | P1 | No |
| T008 | Assert global owner unchanged | WP02 | P1 | No |
