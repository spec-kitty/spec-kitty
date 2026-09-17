---
description: "Work package task list for review-ref-wire-bound (#3954)"
---

# Work Packages: Bound review_ref at the WPStatusChanged wire projection

**Inputs**: Design documents from `kitty-specs/review-ref-wire-bound-01M2QNMY/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, contracts/review_ref_bound.md

**Tests**: Required (ATDD red-first, charter SO#9 / ADR 2026-07-17-1).

**Organization**: One work package (single seam, single owner). Subtasks (`Txxx`) roll up into `WP01`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files).
- Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`.

---

## Work Package WP01: Bound legacy-prose review_ref at the wire projection (Priority: P1) 🎯 MVP

**Goal**: A `WPStatusChanged` moment carrying a >240-byte prose `review_ref` broadcasts (bounded) instead of being dropped whole; pointers ride verbatim; the local status log keeps the full note; exactly one offer per emitted event.
**Independent Test**: Drive `move-task --to approved/done/doing` (and `emit_status_transition`) with a >240-byte multi-line note through the real entry points; assert one offer, bounded one-line `review_ref` (≤240 UTF-8 bytes + `…`), INFO log, and the full note persisted in `status.events.jsonl`; assert an over-bound pointer rides verbatim.
**Prompt**: `/tasks/WP01-bound-review-ref-wire-projection.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-005

### Included Subtasks

T001 [P] RED-first e2e regression tests (T1 approval, T2 completion/multi-hop one-offer, T3 rejection/rework, T4 direct emission) in new `tests/specify_cli/cli/commands/agent/test_move_task_review_ref_broadcast.py`, issue-pinned `@pytest.mark.regression` (#3954), driven through the pre-existing entry points — RED before T003
T002 [P] RED-first seam-unit safety tests (T5 over-bound pointer rides verbatim; T6 codepoint boundary; T7 exactly-one-offer single-hop; T8 over-bound non-review_ref attr untouched) in `tests/status/test_zeitgeist_moment_handler.py` — RED before T003
T003 Implement `_bound_wire_review_ref` helper (pointer-biased structural classifier + one-line collapse + codepoint-safe 240-byte cap with `…`, INFO log) and wire it into `_broadcast_status_transition` before `to_zeitgeist_attrs`, in `src/specify_cli/status/zeitgeist_bridge.py` — turns T001/T002 GREEN
T004 Campsite: correct the stale `_first_non_printable_attr` docstring in the same file (#4318 — names the 8.2.0 pin / missing printability check that 9.1.6 now has)
T005 Verify: full blast-radius test run GREEN, `ruff check`/`ruff format --check`/`mypy` clean; relocate any purely-transitional repro out of `@regression` (durable seam-unit + e2e stay); confirm SUNSET marker + `refs #3954` present

### Implementation Notes

- Order: tests (T001, T002) RED first → helper + wiring (T003) GREEN → campsite (T004) → verify (T005).
- The bound is CLI-side only; do NOT edit the events package, `tasks_move_task.py`, or `emit.py`.
- Byte bound is UTF-8 bytes, not chars; whitespace-collapse precedes the byte check and the printable guard.
- Contract table: `contracts/review_ref_bound.md`.

### Parallel Opportunities

- T001 (new e2e file) and T002 (existing seam-unit file) touch different files → parallel-safe.

### Dependencies

- T003 depends on T001+T002 being RED. T004/T005 depend on T003.

### Risks & Mitigations

- Codepoint split at the 240-byte cut → codepoint-safe truncation + T6 guard.
- Classifier over/under-reach → pointer-biased + fail toward loud pointer-drop; T5/T8 guards.
- Double-offer regression → T7 + existing `recorder.moment_offers()` assertions.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only (T001/T002 → T003 → T004 → T005).
- **MVP Scope**: WP01 is the whole mission.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001..FR-009 | WP01 |
| NFR-001..NFR-003 | WP01 |
| C-001..C-005 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | RED-first e2e regression tests (T1–T4) | WP01 | P1 | Yes |
| T002 | RED-first seam-unit safety tests (T5–T8) | WP01 | P1 | Yes |
| T003 | Implement bound helper + wire into bridge | WP01 | P1 | No |
| T004 | #4318 docstring campsite | WP01 | P2 | No |
| T005 | Verify green + lint/type + relocate transitional | WP01 | P1 | No |
