# Work Packages: The CLI commits its own writes; dirty gates are Mission-scoped

**Inputs**: Design documents from `kitty-specs/cli-owns-its-commits-01M75NTA/`
**Prerequisites**: plan.md, spec.md, research.md, research/code-grounding.md, data-model.md, contracts/cli-observable-behaviour.md, quickstart.md

**Tests**: The bugfix kind (Charter Standing Order 4) requires them. Each WP lands a red test
through the pre-existing CLI entry point before its fix. WP01 is a tidy-first enabler with
its own unit tests.

## Subtask Format: `[Txxx] [P?] Description`

Subtasks are reference rows. Record completion with
`spec-kitty agent tasks mark-status <Txxx> --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `mission_dirt` module: `DirtScope`, `classify_dirt`, `partition_mission_dirt` | WP01 | |
| T002 | Unit tests for every scope, collapsed entries, aliases, Windows separators | WP01 | |
| T003 | Rebuild `coherence._is_other_mission_path` on the module, behaviour pinned | WP01 | |
| T004 | Red test: record-analysis refuses on another Mission's untracked file | WP02 | |
| T005 | Scope the record-analysis gate; warn about foreign dirt (JSON + human) | WP02 | |
| T006 | Re-pin `test_record_analysis_refuses_dirty_worktree_before_write` with an own-Mission control | WP02 | |
| T007 | Red test: single_branch claim refuses on another Mission's directory | WP02 | |
| T008 | Scope the claim gate; warn about another Mission's paths; keep code dirt refusing | WP02 | |
| T009 | Red test: `next` leaves `mission-events.jsonl` untracked in the coordination worktree | WP03 | |
| T010 | `emit_mission_next_invoked` returns the written log path | WP03 | |
| T011 | `next` commits that row in the coordination worktree; warning on refusal | WP03 | |
| T012 | Red test: `setup-plan` leaves lifecycle events uncommitted | WP04 | [P] |
| T013 | `setup-plan` emits PlanCompleted first and commits plan + lifecycle log together | WP04 | |
| T014 | Red test: `mark-status` leaves the status pair dirty on a coordination Mission | WP04 | [P] |
| T015 | `mark-status` commits under auto-commit on every topology | WP04 | |
| T016 | Red test: `init` in a git repository leaves its writes uncommitted | WP05 | |
| T017 | `commit_touched_checkout` accepts a message; `init` baselines and commits | WP05 | |
| T018 | `--no-commit` opt-out; re-pin `test_init_in_existing_repo.py` | WP05 | |

---

## Work Package WP01: Mission-scoped dirt predicate (Priority: P0)

**Goal**: One structural rule for "whose dirt is this path?" (FR-001).
**Independent Test**: `tests/coordination/test_mission_dirt.py` passes; `tests/coordination/test_coherence*.py` stays green.
**Prompt**: `tasks/WP01-mission-dirt-predicate.md`
**Requirement Refs**: FR-001, NFR-001, NFR-002, C-004

### Included Subtasks

T001 `mission_dirt` module (WP01)
T002 Unit tests (WP01)
T003 Rebuild `_is_other_mission_path` on it (WP01)

### Dependencies

- None (starting package).

### Risks & Mitigations

- The destructive guards read `_is_other_mission_path`: keep its result identical (pinned test).

---

## Work Package WP02: Gates count only this Mission's dirt (#7556) (Priority: P1)

**Goal**: `record-analysis` and the single_branch claim stop refusing on another Mission's files (FR-002, FR-003, FR-008).
**Independent Test**: the two red tests turn green; the same-fixture controls keep refusing.
**Prompt**: `tasks/WP02-gates-scope-to-mission.md`
**Requirement Refs**: FR-002, FR-003, FR-008, NFR-001

### Included Subtasks

T004 Red test: record-analysis (WP02)
T005 Scope the record-analysis gate (WP02)
T006 Re-pin the root-dirt test (WP02)
T007 Red test: single_branch claim (WP02)
T008 Scope the claim gate (WP02)

### Dependencies

- Depends on WP01.

---

## Work Package WP03: `next` commits its coordination event row (#5938) (Priority: P1)

**Goal**: A `next`-driven coordination Mission leaves a clean coordination worktree (FR-004).
**Independent Test**: after `next --result success`, `git status` in the coordination worktree is empty.
**Prompt**: `tasks/WP03-next-commits-coordination-row.md`
**Requirement Refs**: FR-004, C-001, C-003

### Included Subtasks

T009 Red test (WP03)
T010 Return the written path (WP03)
T011 Commit it in the coordination worktree (WP03)

### Dependencies

- None.

---

## Work Package WP04: setup-plan and mark-status commit their writes (#3933) (Priority: P2)

**Goal**: No plan-phase or subtask-annotation write is left dirty under auto-commit (FR-005, FR-006).
**Prompt**: `tasks/WP04-setup-plan-and-mark-status-commit.md`
**Requirement Refs**: FR-005, FR-006

### Included Subtasks

T012 Red test: setup-plan (WP04)
T013 Commit plan + lifecycle log together (WP04)
T014 Red test: mark-status on a coordination Mission (WP04)
T015 Commit on every topology under auto-commit (WP04)

### Dependencies

- None.

---

## Work Package WP05: `init` commits what it wrote (#7555) (Priority: P2)

**Goal**: `init` inside a git repository leaves a clean tree (FR-007).
**Prompt**: `tasks/WP05-init-commits-its-writes.md`
**Requirement Refs**: FR-007, C-001, C-002

### Included Subtasks

T016 Red test (WP05)
T017 Baseline + commit through the upgrade committer (WP05)
T018 `--no-commit`; re-pin the existing-repo test (WP05)

### Dependencies

- None.
