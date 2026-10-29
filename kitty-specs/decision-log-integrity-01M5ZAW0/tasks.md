# Work Packages: Decision log integrity

**Inputs**: Design documents from `kitty-specs/decision-log-integrity-01M5ZAW0/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Requested. The mission is ATDD/red-first (charter C-011): each WP lands its failing
acceptance test as its first commit, before any implementation commit.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: deterministic open/retry interleaving tests | WP01 | |
| T002 | Tidy-first: extract the locked open critical section (behaviour-preserving) | WP01 | |
| T003 | Fresh open: artifact write + opening append inside the decisions lock | WP01 | |
| T004 | Retry: check + repair append inside the decisions lock | WP01 | |
| T005 | Stress supplement + docstrings/comments describing the lock scope | WP01 | |
| T006 | Red-first: fold tolerance + reopen-rule-source tests | WP02 | |
| T007 | Re-pin the two stale duplicate-open tests to a differing payload | WP02 | |
| T008 | Fold tolerates identical duplicate openings | WP02 | |
| T009 | Reopen rule from `DECISION_POINT_TERMINAL_REOPEN`; delete local table | WP02 | |
| T010 | Doctor/--repair acceptance over a duplicated log; CHANGELOG entry | WP02 | |

---

## Work Package WP01: One opening per decision under concurrent opens (Priority: P1)

**Goal**: `open_decision` holds `decisions/index.json.lock` across the dedup lookup, index
append, artifact write and opening append (fresh path), and across the existence check and the
repair append (retry path).
**Independent Test**: `tests/specify_cli/decisions/test_service_open_concurrency.py` — paused
first open + identical second open → 1 opening row; interrupted open + two paused retries → 1 row.
**Prompt**: `tasks/WP01-open-path-under-decisions-lock.md`
**Requirement Refs**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-002

### Included Subtasks

T001 Red-first: deterministic open/retry interleaving tests (WP01)
T002 Tidy-first: extract the locked open critical section (WP01)
T003 Fresh open: artifact write + opening append inside the decisions lock (WP01)
T004 Retry: check + repair append inside the decisions lock (WP01)
T005 Stress supplement + docstrings/comments describing the lock scope (WP01)

### Implementation Notes

- Mirror #6294's terminal-path structure (`_terminal_command` holds one lock across everything).
- Keep `open_decision` ≤ 15 complexity; the locked section is a helper.

### Parallel Opportunities

- None inside the WP (one file). WP02 touches disjoint files.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Lock-order inversion → verified decisions → status only (research.md R-2); keep emit inside.
- Longer hold → one append per call (NFR-002); the existing bounded wait stays.

---

## Work Package WP02: Duplicated logs fold; reopen rule from the events package (Priority: P2)

**Goal**: The fold accepts identical duplicate openings (operator ruling 1), refuses differing
ones, and reads the reopen rule from `spec_kitty_events` (operator ruling 2).
**Independent Test**: `tests/specify_cli/decisions/test_index_fold_duplicate_open.py` plus the
doctor/--repair case in `tests/decisions/test_decisions_reconciler.py`.
**Prompt**: `tasks/WP02-fold-tolerance-and-reopen-rule.md`
**Requirement Refs**: FR-003, FR-004, C-003

### Included Subtasks

T006 Red-first: fold tolerance + reopen-rule-source tests (WP02)
T007 Re-pin the two stale duplicate-open tests to a differing payload (WP02)
T008 Fold tolerates identical duplicate openings (WP02)
T009 Reopen rule from DECISION_POINT_TERMINAL_REOPEN; delete local table (WP02)
T010 Doctor/--repair acceptance over a duplicated log; CHANGELOG entry (WP02)

### Implementation Notes

- Tolerance compares payloads with `recorded_at` removed; picks the min by `(recorded_at, event_id)`.
- `is_allowed_terminal_reopen` keeps its signature (callers in `service.py` and
  `consolidation/drivers.py` are unchanged).

### Parallel Opportunities

- File-disjoint from WP01; sequenced after it only so the CHANGELOG entry covers both.

### Dependencies

- Depends on WP01.

### Risks & Mitigations

- Over-tolerance → the differing-payload case is the same-fixture positive control.
- Order dependence (merge driver re-sorts) → tests feed rows in both orders.
