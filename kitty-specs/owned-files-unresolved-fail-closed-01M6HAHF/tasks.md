# Work Packages: Owned files unresolved fail closed

**Mission**: `owned-files-unresolved-fail-closed-01M6HAHF` · **Branch**: `fix/7149-ownership-unresolved` (planning, base and consolidation target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/evidence-codes.md](contracts/evidence-codes.md)

Two independent work packages with non-overlapping `owned_files`. They can run in parallel lanes. WP01 is the P0 critical path (#7149's fail-closed bullet).

## Subtask Format: `[Txxx] [P?] Description`

`[P]` marks a subtask that is safe to run in parallel with the others (different files). Completion is recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`; the rows below are references, not checkboxes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests: unresolved ownership (task file absent, `tasks/` missing, unreadable task file) yields `OWNERSHIP_UNRESOLVED` naming the read location; positive control and the authored-empty ratchet | WP01 | |
| T002 | Register `OWNERSHIP_UNRESOLVED` and `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED` in the code families and the code-literal test | WP01 | |
| T003 | Carry the `tasks/` read location in the scan; `_judge` emits the unresolved verdict before the owned-change test | WP01 | |
| T004 | Recovery line for `OWNERSHIP_UNRESOLVED` | WP01 | |
| T005 | Attestation refuses the unresolved verdict (unliftable set and refusal text), red-first with a resolved control | WP01 | |
| T006 | Orchestrator-api envelope code-registry comment | WP01 | [P] |
| T007 | `acceptably_canceled_wp_ids` takes the optional `owned` fact and reads through the placement seam | WP02 | |
| T008 | `accept` passes `run.owned` at both canceled-read call sites | WP02 | |
| T009 | Red-first owned-accept test: Mission absent from the repository root, one operator-canceled work package | WP02 | |
| T010 | Owned move-task: an empty `owned_files` declaration gets its own refusal detail naming the task file | WP02 | [P] |
| T011 | Strengthen the owned move-task test to assert both refusal details on one fixture | WP02 | [P] |

## Work Package WP01: Unresolved-ownership verdict and attestation refusal (Priority: P0) 🎯 MVP

**Goal**: An approved work package whose ownership declaration cannot be read is refused with `OWNERSHIP_UNRESOLVED` (or `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED`), which names the location read, is checked before `IMPLEMENTATION_MISSING`, and cannot be lifted by `--attest-no-implementation`.
**Independent test**: a Mission whose approved work package's task file is removed is refused with the new code naming `tasks/`; the same fixture with the file present passes; an authored `owned_files: []` still yields `IMPLEMENTATION_MISSING`.
**Prompt**: [tasks/WP01-unresolved-ownership-verdict.md](tasks/WP01-unresolved-ownership-verdict.md)
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-008, NFR-001, NFR-002, NFR-003, C-001, C-002

### Included Subtasks

T001 Red-first tests for the unresolved verdict (WP01)
T002 Register the new codes (WP01)
T003 Scan carries the read location; `_judge` checks unresolved first (WP01)
T004 Recovery line (WP01)
T005 Attestation refuses the unresolved verdict (WP01)
T006 Orchestrator-api envelope registry comment (WP01)

### Implementation Notes

Tests first (T001, T005's red half), then T002 → T003 → T004 → T005 → T006. The verdict lives only in `wp_evidence`; callers (`accept`, `consolidate`, `orchestrator-api`) pick it up through `mission_evidence_report` / `evaluate_evidence` unchanged.

### Parallel Opportunities

T006 is a comment-only edit in another file.

### Dependencies

None.

### Risks & Mitigations

- Open PR #7146 also edits `wp_evidence.py`. Keep edits inside `_Scan`, `_owned_patterns_by_wp`, `_judge`, the code constants and `_RECOVERY`; rebase at closeout.
- Over-firing on authored empty lists. The authored-empty ratchet (`test_owned_acceptance_authority_6023.py::missing_owned_ownership`) must stay `IMPLEMENTATION_MISSING`.

## Work Package WP02: Owned-checkout canceled read and honest move-task detail (Priority: P1)

**Goal**: `accept --owned-checkout` reads the operator-canceled work packages from the owned checkout, and the owned review-ward `move-task` says when a work package declares no `owned_files`.
**Independent test**: an owned-checkout Mission absent from the repository root, with one operator-canceled work package, is accepted with that work package excluded; the owned move-task refusal for `owned_files: []` names the task file while keeping `OWNED_IMPLEMENTATION_MISSING`.
**Prompt**: [tasks/WP02-owned-canceled-read-and-move-task-detail.md](tasks/WP02-owned-canceled-read-and-move-task-detail.md)
**Requirements**: FR-006, FR-007, NFR-002, NFR-003, C-003

### Included Subtasks

T007 `acceptably_canceled_wp_ids` takes `owned` (WP02)
T008 `accept` passes `run.owned` at both call sites (WP02)
T009 Red-first owned-accept canceled test (WP02)
T010 Owned move-task empty-declaration detail (WP02)
T011 Strengthen the owned move-task test (WP02)

### Implementation Notes

T009's red half first, then T007 → T008. T010 and T011 are independent of T007–T009.

### Parallel Opportunities

T010/T011 run alongside T007–T009 (different files).

### Dependencies

None (independent of WP01; no shared files).

### Risks & Mitigations

- `tasks_move_task.py` is also edited by open PR #7146. Touch only `_mt_require_owned_implementation`'s `not patterns` branch.
- The other `acceptably_canceled_wp_ids` callers (`orchestrator_api/consolidation.py`, `done_bookkeeping.py:783`, `preflight.py`) keep calling without `owned` and must behave exactly as before.
