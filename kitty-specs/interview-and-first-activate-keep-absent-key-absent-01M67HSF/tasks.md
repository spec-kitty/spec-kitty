# Tasks: Interview and first activate keep an absent activation key absent

**Mission**: `interview-and-first-activate-keep-absent-key-absent-01M67HSF` · **Issue**: #6685 (refs #6629, #6683, #6408, #4253, #4400)
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | End-to-end red-first reproduction for the interview writer | WP01 | |
| T002 | The interview promotes into present lists only | WP01 | |
| T003 | Focused interview tests: absent, present, narrowed, denied, idempotent | WP01 | |
| T004 | The FR-015 acceptance row for the interview caller | WP01 | |
| T005 | End-to-end red-first reproduction for the first activation | WP02 | |
| T006 | `plan_activation` keeps an in-force artifact implicit | WP02 | |
| T007 | Activation pins: #4253 rows, freeze-warning rows, `--only` ratchet, skill/mission-type ratchet | WP02 | |
| T008 | The FR-015 acceptance row for the activating caller | WP02 | |
| T009 | Docstrings that name the seeding as a residual | WP03 | [P] |
| T010 | Operator docs for `charter interview` and `charter activate` | WP03 | [P] |
| T011 | CHANGELOG entry | WP03 | [P] |
| T012 | Targeted gates: terminology, docs freshness, effective-set seam, kind vocabulary | WP03 | [P] |

## Phase 1 — The interview stops filling an absent key

### WP01 — Interview promotes into present lists only (P1)

**Goal**: `charter interview` never turns an absent `activated_<kind>` key into a list. It promotes into a present list exactly as today, and it names each key it left absent, the reason (the whole kind is in force), and `--narrow-activation`. `charter synthesize --dry-run --json` after an interview on a fresh project reports `fresh_project_seed_dry_run`.
**Independent test**: the new end-to-end test drives `charter interview` and then `charter synthesize --dry-run --json`; it is red on main (two lists, 38 + 14 entries) and green after the change.
**Prompt**: [tasks/WP01-interview-present-lists-only.md](tasks/WP01-interview-present-lists-only.md)

Requirement refs: FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002, SC-001, SC-003, SC-004, C-001, C-002, C-003, C-007

Included subtasks:

T001 End-to-end red-first reproduction for the interview writer (WP01)
T002 The interview promotes into present lists only (WP01)
T003 Focused interview tests: absent, present, narrowed, denied, idempotent (WP01)
T004 The FR-015 acceptance row for the interview caller (WP01)

Dependencies: none. Risks: the new message must not read as a failure; the denied-id skip must keep working on the present-list path; several absent-key fixtures in `test_charter_interview_promotion.py` must become present-list fixtures without losing their assertions.

## Phase 2 — The first activation keeps an in-force artifact implicit

### WP02 — `charter activate` writes no list for an artifact already in force (P1)

**Goal**: on an absent key of an `all`-when-absent kind, activating an artifact the in-force set already holds writes no allow list and says so; every other case (`mission-type`, `skill`, unresolved set, artifact not in force, deny-only) behaves exactly as today.
**Independent test**: the new end-to-end test drives `charter activate directive <id>` and then `charter synthesize --dry-run --json`; the #4253 tests assert zero drop with the key still absent.
**Prompt**: [tasks/WP02-activate-keeps-in-force-implicit.md](tasks/WP02-activate-keeps-in-force-implicit.md)

Requirement refs: FR-003, FR-004, FR-005, FR-006, FR-008, NFR-002, SC-002, SC-003, SC-004, C-001, C-003, C-005, C-006, C-007

Included subtasks:

T005 End-to-end red-first reproduction for the first activation (WP02)
T006 `plan_activation` keeps an in-force artifact implicit (WP02)
T007 Activation pins: #4253 rows, freeze-warning rows, `--only` ratchet, skill/mission-type ratchet (WP02)
T008 The FR-015 acceptance row for the activating caller (WP02)

Dependencies: WP01 (shares the end-to-end test file). Risks: the freeze-warning tests must move to the rows that still materialise; the `resynthesize` acceptance row's preflight assertion must compare against the in-force set without weakening.

## Phase 3 — Docs, docstrings and the record

### WP03 — Say it in the docstrings, the docs and the changelog (P2)

**Goal**: the two writers' docstrings, the operator docs and the CHANGELOG state that an absent key is never filled and how to choose a list instead; the targeted gates stay green.
**Independent test**: `pytest tests/architectural/test_no_legacy_terminology.py`, `test_fr015_effective_set_seam_is_public`, the kind-vocabulary gate and `check_docs_freshness --ci` (errors=0).
**Prompt**: [tasks/WP03-docs-docstrings-changelog.md](tasks/WP03-docs-docstrings-changelog.md)

Requirement refs: FR-009, FR-010, NFR-003, SC-001, SC-002

Included subtasks:

T009 Docstrings that name the seeding as a residual (WP03)
T010 Operator docs for `charter interview` and `charter activate` (WP03)
T011 CHANGELOG entry (WP03)
T012 Targeted gates: terminology, docs freshness, effective-set seam, kind vocabulary (WP03)

Dependencies: WP01, WP02.

## MVP

WP01 fixes half the reported defect and unblocks a project whose first charter step is the interview; WP01 + WP02 together close #6685. WP03 keeps the record and the gates honest.
