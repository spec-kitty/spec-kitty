# Work Packages: Rework is not an override

**Inputs**: Design documents from `kitty-specs/rework-is-not-an-override-01M3MQV6/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: explicitly required. The spec mandates ATDD red-first (NFR-004, charter C-011), so each WP's first lane commit is its failing acceptance test.

**Organization**: fine-grained subtasks (`Txxx`) roll up into 4 work packages. Owned files are strictly disjoint. Each WP owns its own RED-first acceptance file, and WP01 owns only the shared harness plus the controls that are green on the base.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Real-CLI rework-loop harness (distinct-tool identities, every hop via move-task) | WP01 | |
| T002 | Five override probes + review-cycle artifact lister | WP01 | |
| T003 | Ratchet: genuine for_review-source override lights all five probes | WP01 | [P] |
| T004 | Ratchet: unrelated agent refused on an occupied slot / `in_review` verdict | WP01 | [P] |
| T005 | Ratchet: `agent action implement` rework stays unforced, no override | WP01 | [P] |
| T006 | Ratchet: an intervening annotation does not hide a genuine override | WP01 | [P] |
| T007 | RED: unforced two-cycle loop across 3 rejection routes | WP02 | |
| T008 | `status/review_roles.py::latest_implementer_actor` + facade + unit truth table | WP02 | |
| T009 | `MoveTaskRequest.latest_implementer` + guard allow-arms + unit rows | WP02 | |
| T010 | Resolve `latest_implementer` in pass 1 (fail-closed read) | WP02 | |
| T011 | Green-up, un-mark regression, named gates, lint/type | WP02 | |
| T012 | Tidy-first: characterize + split `_is_arbiter_override` into a pure predicate | WP03 | |
| T013 | RED: forced rework is not an override; in_review-source override recorded | WP03 | |
| T014 | Narrow classification + re-pin stale over-match unit pins | WP03 | |
| T015 | Approved-cycle suppression + `done` row coverage | WP03 | |
| T016 | Green-up, un-mark regression, named gates, lint/type | WP03 | |
| T017 | RED guard: shipped guidance has no ordinary-loop `--force` | WP04 | |
| T018 | implement-review skill guidance | WP04 | [P] |
| T019 | runtime-review skill + review checklist guidance | WP04 | [P] |
| T020 | how-to guide `review-work-package.md` | WP04 | [P] |
| T021 | Green-up, doctrine/skill tests, terminology + docs freshness | WP04 | |

---

## Work Package WP01: Acceptance harness and ratchet controls (Priority: P0)

**Goal**: a shared real-CLI harness that drives the review loop hop by hop, with implementer, reviewer and third-agent identities on distinct tools. It carries the five override probes, plus the behaviour that is green on the base and must stay green.
**Independent Test**: `test_rework_guard_ratchets.py` passes on the planning base and pins FR-006, FR-008, the FR-005 for_review source and the US3 annotation case.
**Prompt**: `tasks/WP01-acceptance-harness-and-ratchets.md`
**Requirement Refs**: FR-005, FR-006, FR-008

### Included Subtasks

T001 Real-CLI rework-loop harness (WP01)
T002 Five override probes + review-cycle artifact lister (WP01)
T003 Ratchet: genuine for_review-source override lights all five probes (WP01)
T004 Ratchet: unrelated agent refused on an occupied slot / in_review verdict (WP01)
T005 Ratchet: agent action implement rework stays unforced (WP01)
T006 Ratchet: an intervening annotation does not hide a genuine override (WP01)

### Implementation Notes

The harness must never seed rework hops with past timestamps (research R-07 fixture warning); only the initial `genesis → planned` may be seeded. Every probe must be proven non-vacuous by T003 on the same fixture shape.

### Parallel Opportunities

T003–T006 are independent tests in one file.

### Dependencies

None.

### Risks & Mitigations

Blind probes (the tactic `acceptance-criteria-non-vacuity`): T003 is the positive control for every probe.

**Estimated prompt size**: ~330 lines

---

## Work Package WP02: Ownership guard role allow-arms (Priority: P1)

**Goal**: the latest implementer resumes and resubmits rework, and a non-implementer claims, approves or rejects from `for_review`, all via `move-task` without `--force`. Unrelated agents stay refused.
**Independent Test**: `test_rework_unforced_loop.py` is RED on the base and GREEN at the end, for all 3 rejection routes, with 0 `force: true` events after each rejection.
**Prompt**: `tasks/WP02-ownership-guard-role-allow-arms.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-006

### Included Subtasks

T007 RED: unforced two-cycle loop across 3 rejection routes (WP02)
T008 status/review_roles.py latest_implementer_actor + facade + unit truth table (WP02)
T009 MoveTaskRequest.latest_implementer + guard allow-arms + unit rows (WP02)
T010 Resolve latest_implementer in pass 1 (WP02)
T011 Green-up, un-mark regression, named gates, lint/type (WP02)

### Dependencies

Depends on WP01 (harness).

### Risks & Mitigations

Generic actors and review-verdict events must be excluded from the projection (contract). The refusal `error` string is pinned byte-exact, so any hint goes in `console_warning` only. Complexity stays ≤ 15.

**Estimated prompt size**: ~380 lines

---

## Work Package WP03: Arbiter override classification narrowed (Priority: P1)

**Goal**: an arbiter override is recorded only for a forced `planned → approved|done` after a rejection from `for_review` or `in_review`. A forced rework is never an override.
**Independent Test**: `test_rework_override_classification.py` is RED on the base (over-match + under-match) and GREEN at the end, with all five probes consistent.
**Prompt**: `tasks/WP03-arbiter-override-classification.md`
**Requirement Refs**: FR-004, FR-005

### Included Subtasks

T012 Tidy-first: characterize + split _is_arbiter_override into a pure predicate (WP03)
T013 RED: forced rework is not an override; in_review-source override recorded (WP03)
T014 Narrow classification + re-pin stale over-match unit pins (WP03)
T015 Approved-cycle suppression + done row coverage (WP03)
T016 Green-up, un-mark regression, named gates, lint/type (WP03)

### Dependencies

Depends on WP01 (harness probes). Runs in parallel with WP02 (disjoint files).

**Estimated prompt size**: ~340 lines

---

## Work Package WP04: Guidance matches the unforced loop (Priority: P2)

**Goal**: the shipped skills and the how-to guide stop instructing `--force` for ordinary reject/rework/re-review, and keep the arbiter, self-review and done-override guidance.
**Independent Test**: `tests/doctrine/test_rework_guidance_unforced.py` is RED on the base and GREEN at the end, and the skill content tests pass.
**Prompt**: `tasks/WP04-guidance-unforced-loop.md`
**Requirement Refs**: FR-007

### Included Subtasks

T017 RED guard: shipped guidance has no ordinary-loop --force (WP04)
T018 implement-review skill guidance (WP04)
T019 runtime-review skill + review checklist guidance (WP04)
T020 how-to guide review-work-package.md (WP04)
T021 Green-up, doctrine/skill tests, terminology + docs freshness (WP04)

### Dependencies

Depends on WP02 and WP03: the guidance must describe shipped behaviour.

**Estimated prompt size**: ~260 lines

---

## Dependency & Execution Summary

- **Sequence**: WP01 → (WP02 ∥ WP03) → WP04.
- **Parallelization**: WP02 and WP03 own disjoint files and can run in separate lanes.
- **MVP Scope**: WP01 + WP02 (the unforced loop).

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP02 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP03 |
| FR-005 | WP01 (for_review ratchet), WP03 (in_review build) |
| FR-006 | WP01 (ratchet), WP02 (kept green) |
| FR-007 | WP02 (refusal hint), WP04 (shipped guidance) |
| FR-008 | WP01 |
