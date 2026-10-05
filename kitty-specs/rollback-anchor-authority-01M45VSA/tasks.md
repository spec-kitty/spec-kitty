# Work Packages: Rollback anchor authority (#5686, #5666)

**Inputs**: `kitty-specs/rollback-anchor-authority-01M45VSA/` — spec.md, plan.md, data-model.md, quickstart.md, research/code-grounding.md
**Prerequisites**: plan.md, spec.md, data-model.md

**Tests**: required. Red-first per charter SO #4 / C-011: each WP commits its failing test(s) before the fix.

**Organization**: subtasks (`Txxx`) roll up into work packages (`WPxx`). Each work package has its own prompt in `tasks/`.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows. Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Rewrite the #5666 reproduction to drive the gate through the door; drop its `p0_repro` marker | WP01 | |
| T002 | Delete `_rollback_target_after_failed_reconciliation` and its call; gate FAIL/REFUSE only raises `Exit(1)` | WP01 | |
| T003 | Widen the AST pin (retired name; no `restore_branch_ref` in the executor family outside `rollback.py`; self-mutation case) | WP01 | |
| T004 | Re-pin `test_refuse_restores_target.py` and retire `TestRollbackTargetAfterFailedReconciliation` | WP01 | |
| T005 | Door-level FAIL with concurrent target commit + clean-checkout positive control in `tests/terminus/test_rollback_door.py` | WP01 | [P] |
| T006 | Atomic `save_state` + new `ConsolidationState` fields with fail-closed loaders | WP02 | |
| T007 | `begin_attempt` classification (restore target from record, unsettled marks, unexplained list) + `classify` pre-check API | WP02 | |
| T008 | Intent chains: `note_advance_intent`, effective post, clearing helpers | WP02 | |
| T009 | `_rollback_branch`: effective post, settle/unsettle marks, `KEPT_BY_OPERATOR` release outcome | WP02 | |
| T010 | Re-pin truth table and between-attempts tests; own-moves rule tests | WP02 | |
| T011 | `git/ref_advance.py`: advance-intent sink (ContextVar) in `advance_branch_ref` + `advance_branch_ref_for_commit`; restore resync accepts a checkout already at the target | WP06 | [P] |
| T012 | Phase recorder: entry-expected taint check (FR-011) and per-branch intent clearing | WP03 | |
| T013 | Executor: early `UNEXPLAINED_BRANCH_MOVE` pre-check before attestations/heal; intent sink installed around the door span; `begin_attempt` gets this process's pre-claim tips | WP03 | |
| T014 | Settle the target once the door span completes (PASS + projection proof) | WP03 | |
| T015 | Kill-window, orderly-exit, pre-attestation and between-phase production-path tests; drop the #5686 `p0_repro` marker | WP03 | |
| T016 | `consolidate --abort --release-branch/--release-reason` option, validation (`RELEASE_BRANCH_INVALID`) and persistence | WP04 | |
| T017 | Truthful abort success line and report for kept branches | WP04 | |
| T018 | CLI tests: release unblocks a NOT-restored abort; release never keeps a provable landing; invalid usages refuse | WP04 | |
| T019 | ADR 2026-09-19-1 dated follow-up 2026-10-05 | WP05 | [P] |
| T020 | CLAUDE.md consolidation section: remaining second restore paths, new codes | WP05 | [P] |
| T021 | Changelog entry and operator docs (troubleshoot-merge, cli-commands) | WP05 | [P] |

---

## Work Package WP01: Retire the FAIL-path restore (#5666) (Priority: P1)

**Goal**: A reconciliation FAIL/REFUSE rolls back only through the single door, which compare-and-swaps against the recorded post tip, so a concurrent target commit is never discarded.
**Independent Test**: `tests/consolidation/test_rollback_anchor_p0_repro.py::test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit` (rewritten, unmarked) plus the door FAIL test.
**Prompt**: `tasks/WP01-retire-fail-path-restore.md`
**Requirement Refs**: FR-001, FR-002, FR-010, SC-003

### Included Subtasks

T001 Rewrite the #5666 reproduction to drive the gate through the door; drop its `p0_repro` marker (WP01)
T002 Delete `_rollback_target_after_failed_reconciliation` and its call (WP01)
T003 Widen the AST pin with a self-mutation case (WP01)
T004 Re-pin `test_refuse_restores_target.py`; retire the helper's unit tests (WP01)
T005 Door-level FAIL + concurrent commit + positive control (WP01)

### Dependencies

- None.

### Risks & Mitigations

- Gate tests that pinned the helper as the restorer must move to the door, not be deleted wholesale (stale → re-pin).

---

## Work Package WP02: Record-anchored rollback authority (#5686) (Priority: P1)

**Goal**: `consolidation/rollback.py` derives every restore target and CAS expectation from the persisted record: unsettled marks, provable intent chains, carried restore targets and the operator-release outcome.
**Independent Test**: `test_second_abort_never_reports_restored_over_an_unrecorded_landing` (unmarked) plus the re-pinned authority unit tests.
**Prompt**: `tasks/WP02-record-anchored-rollback-authority.md`
**Requirement Refs**: FR-003, FR-004, FR-006, FR-007, FR-008, FR-010, NFR-001, NFR-004

### Included Subtasks

T006 Atomic `save_state` + new fields (WP02)
T007 `begin_attempt` classification + pre-check API (WP02)
T008 Intent chains and effective post (WP02)
T009 `_rollback_branch` settle/unsettle + `KEPT_BY_OPERATOR` (WP02)
T010 Re-pin authority tests; own-moves rule tests (WP02)

### Dependencies

- None. It runs in parallel with WP01 and WP06, with disjoint files.

---

## Work Package WP03: Wire the authority into consolidate (Priority: P1)

**Goal**: The executor and the phase recorder feed the authority: intents persisted ahead of every advance in the span, a recorder that refuses to adopt a foreign interleave, an early `UNEXPLAINED_BRANCH_MOVE` refusal, and target settling after a completed span.
**Independent Test**: new kill-window tests (subprocess `os._exit`) and the between-phase foreign-commit door test.
**Prompt**: `tasks/WP03-wire-authority-into-consolidate.md`
**Requirement Refs**: FR-005, FR-006, FR-010, FR-011, SC-001, SC-002, SC-003

### Included Subtasks

T012 Recorder taint + per-branch intent clearing (WP03)
T013 Executor pre-check, sink installation, pre-claim tips (WP03)
T014 Settle the target after a completed door span (WP03)
T015 Kill-window and between-phase tests (WP03)

### Dependencies

- Depends on WP01, WP02, WP06.

---

## Work Package WP06: Git plumbing: advance-intent sink and lagging-checkout restore (Priority: P1)

**Goal**: `git/ref_advance.py` reports (branch, old, new) to an injected sink before every CAS advance, and a restore accepts a checkout already at the restore target.
**Independent Test**: `tests/git/test_ref_advance_intent_sink.py`, `tests/git/test_restore_branch_ref_resync.py`.
**Prompt**: `tasks/WP06-git-plumbing-intent-sink.md`
**Requirement Refs**: FR-006, FR-012, C-006

### Included Subtasks

T011 Advance-intent sink + lagging-checkout restore (WP06)

### Dependencies

- None (phase 1, in parallel with WP01 and WP02). It has fewer subtasks than the 3-subtask guideline on purpose: the post-tasks squad split this disjoint plumbing slice out of WP03 to keep WP03 reviewable.

---

## Work Package WP04: Operator release and truthful `--abort` (#5687 deadlock) (Priority: P2)

**Goal**: `consolidate --abort --release-branch <b> --release-reason <text>` keeps a NOT-restored branch at its live tip, so `--abort` never deadlocks. The text never claims a kept branch was restored.
**Independent Test**: CLI tests in `tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`.
**Prompt**: `tasks/WP04-operator-release-truthful-abort.md`
**Requirement Refs**: FR-008, FR-009, SC-002

### Included Subtasks

T016 Option, validation, persistence (WP04)
T017 Truthful success line and report (WP04)
T018 CLI tests (WP04)

### Dependencies

- Depends on WP02.

---

## Work Package WP05: Docs, ADR and changelog (Priority: P3)

**Goal**: Record the decision (ADR follow-up), keep CLAUDE.md's residual list honest, and add a changelog entry.
**Prompt**: `tasks/WP05-docs-adr-changelog.md`
**Requirement Refs**: C-001, C-002

### Included Subtasks

T019 ADR follow-up (WP05)
T020 CLAUDE.md (WP05)
T021 Changelog (WP05)

### Dependencies

- Depends on WP03, WP04, WP06.
