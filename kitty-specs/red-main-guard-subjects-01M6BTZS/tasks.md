# Work Packages: Clear the two pre-existing contract-guard reds (#6997)

**Inputs**: Design documents from `/kitty-specs/red-main-guard-subjects-01M6BTZS/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md

**Tests**: The two reds ARE tests. The only test-file edit is an added named code in
an existing assertion list (FR-005); no new test file is created.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into work packages (`WPxx`).
Each work package is independently deliverable and testable: WP01 clears the
terminology guard, WP02 clears the orchestrator contract guard.

**Prompt Files**: `tasks/WP01-unclog-ci-branch-intent-wording.md` and
`tasks/WP02-register-safe-commit-directory-code.md`.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log
  snapshot is the sole subtask-completion authority — there is no `- [ ]` box to tick.

## Path Conventions

- **Single project**: `src/`, `tests/`, `docs/` at the repository root.

---

## Work Package WP01: The unclog-ci page's branch-intent wording (Priority: P1) 🎯 MVP

**Goal**: Reword the one live-doc sentence that trips the branch-intent terminology
guard, keeping the fact it states, so the guard is green without being edited.
**Independent Test**: Run the terminology guard on the reworded page (green), then
revert only the sentence and run it again (red on `unclog-ci.md`). The guard file's
bytes are unchanged throughout (`git diff --stat` shows no change under
`tests/contract/test_terminology_guards.py`).
**Prompt**: `/tasks/WP01-unclog-ci-branch-intent-wording.md`
**Requirement Refs**: FR-001, NFR-001, C-001, SC-002

### Included Subtasks

T001 Reword `docs/development/how-to/unclog-ci.md` line 95 so the trunk-merge CI-wave fact survives without the deprecated phrasing
T002 [P] Sweep every live first-party doc for the other forbidden patterns and record the result (expected: only exempt `docs/adr/**` hits)
T003 Prove the guard is red before and green after with the guard file untouched

### Implementation Notes

- The sentence "Every GitHub PR merge to `main` starts a new wave" is descriptive, not
  instructional; the fix keeps "a PR landing causes a new CI wave" and drops the
  wording the branch-intent governance retired. The two preceding sentences already
  name `main` as the trunk that moves, so the reworded sentence need not repeat it.
- Stay inside the page's existing 100-column wrap; the diff must read as a wording
  change, not a reflow.
- Do not use a synonym swap that leaves the sentence reading as an instruction to
  merge in `main`; the guard's intent (and the charter's Branch-Intent Terminology
  Governance section) is the constraint, not the literal grep.

### Parallel Opportunities

- T002 is independent of T001's wording choice and can run first.

### Dependencies

- None. WP01 and WP02 are independent and may run in parallel.

### Risks & Mitigations

- Risk: a grep-dodging synonym swap. Mitigation: the reviewer checks the sentence
  reads as description, and T003's revert proof shows the guard still fires on the
  original text.

---

## Work Package WP02: Register `SAFE_COMMIT_DIRECTORY_ARGUMENT` in the orchestrator contract (Priority: P1)

**Goal**: `orchestrator_api.allowed_error_codes` admits every code the safe-commit path
emits, both contract copies stay identical, and the two prose enumerations agree.
**Independent Test**: Run
`tests/contract/test_orchestrator_api.py::TestAllowedErrorCodes::test_safe_commit_failure_codes_are_contract_allowed`
(red before, green after) and
`tests/specify_cli/core/test_contract_gate.py::test_vendored_contract_matches_planning_artifact`
(green after; a one-sided edit makes it red).
**Prompt**: `/tasks/WP02-register-safe-commit-directory-code.md`
**Requirement Refs**: FR-002, FR-003, FR-004, FR-005, FR-006, NFR-002, C-002, C-003, SC-003, SC-004

### Included Subtasks

T004 Add `SAFE_COMMIT_DIRECTORY_ARGUMENT` to `orchestrator_api.allowed_error_codes` in `src/specify_cli/core/upstream_contract.json`
T005 Mirror the same insertion in `docs/contracts/upstream-3.0.0-shape.json` so the two documents are byte-identical
T006 [P] Add the code to the prose enumerations: `docs/api/orchestrator-api.md`'s error-code list and the operator skill's error-code table
T007 [P] Name `SAFE_COMMIT_DIRECTORY_ARGUMENT` in the contract test's explicit code list, without changing the descendant walk
T008 Add the changelog entry as a per-PR fragment in `docs/changelog/unreleased/`
T009 Bump `CONTRACT_VERSION` to 1.22.0 with its ledger comment, docs entry and pinned test assertions

### Implementation Notes

- Follow precedent `46f37835ca` (#5443): same four surfaces, same ordering convention
  (insert next to its sibling safe-commit codes), same changelog shape.
- The code is a **pre-mutation** refusal (`preflight_commit` raises it before HEAD,
  refs or the index move) carrying `offending_path`; it is NOT a
  `SAFE_COMMIT_RECOVERY_FAILED` refinement. Say so where the enumerations explain the
  codes.
- Do not touch `kitty-specs/064-complete-mission-identity-cutover/contracts/` (frozen,
  SK-154) and do not touch anything under `packs/` (generated trees).

### Parallel Opportunities

- T006 and T007 touch disjoint files and can run alongside T004/T005.

### Dependencies

- None. Independent of WP01.

### Risks & Mitigations

- Risk: a one-sided JSON edit fails the equality gate. Mitigation: edit both copies in
  the same commit and run the equality test.
- Risk: describing the code as a recovery refinement misleads orchestrator authors
  about whether a commit landed. Mitigation: state "refused before any commit".

---

## Dependency & Execution Summary

- **Sequence**: WP01 and WP02 are independent; either order, or in parallel.
- **Parallelization**: both WPs can run concurrently (disjoint file sets).
- **MVP Scope**: WP01 alone clears one of the two reds; both are needed for #6997.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP02 |
| FR-004 | WP02 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| NFR-001 | WP01 |
| NFR-002 | WP02 |
| NFR-003 | WP01, WP02 |
| C-001 | WP01, WP02 |
| C-002 | WP02 |
| C-003 | WP02 |
| SC-001 | WP01, WP02 |
| SC-002 | WP01 |
| SC-003 | WP02 |
| SC-004 | WP02 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Reword the unclog-ci trunk-merge sentence | WP01 | P1 | No |
| T002 | Sweep live docs for the other forbidden patterns | WP01 | P1 | Yes |
| T003 | Prove the guard red before / green after with the guard file untouched | WP01 | P1 | No |
| T004 | Register the code in the vendored contract | WP02 | P1 | No |
| T005 | Mirror it in the pinned contract copy | WP02 | P1 | No |
| T006 | Mirror it in the two prose enumerations | WP02 | P1 | Yes |
| T007 | Name the code in the contract test's explicit list | WP02 | P1 | Yes |
| T008 | Add the changelog entry as a per-PR fragment | WP02 | P1 | No |
| T009 | Bump the contract version and its pinned assertions | WP02 | P1 | No |
