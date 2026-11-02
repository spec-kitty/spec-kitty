# Work Packages: Pre-review gate scope recovery

**Inputs**: Design documents from `/kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required — every fix in this mission is red-first through a pre-existing
entry point (charter, ATDD-First Discipline).

**Organization**: Fine-grained subtasks (`Txxx`) roll up into one work package
(`WP01`). The mission is one coherent change across four production modules; a
second work package would only split a single invariant.

**Prompt Files**: `tasks/WP01-scope-key-budget-shape-and-diagnostics.md`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first: WP-model + subtask-roster test for `pre_review_test_scope` | WP01 | no |
| T002 | Red-first: review-budget shape-resolution test module | WP01 | yes |
| T003 | Red-first: refusal-diagnostic content test module | WP01 | yes |
| T004 | Declare `pre_review_test_scope` on `WPMetadata` | WP01 | no |
| T005 | Whole-command budget default + `whole_command` selector in `review/test_timeout.py` | WP01 | no |
| T006 | Wire the shape probe at the one budget-resolution seam in `tasks_move_task_gates.py` | WP01 | no |
| T007 | Shape-aware refusal reasons in `review/pre_review_gate.py` and the console renderer | WP01 | no |
| T008 | Docs, changelog fragment, targeted suites and docs-freshness verification | WP01 | no |

---

## Work Package WP01: Scope key, budget shape and actionable refusals (Priority: P1) 🎯 MVP

**Goal**: A `for_review` move in a repository with a whole-suite review command
completes inside a budget that matches that command, the documented per-WP
bounded-scope recovery parses and is honoured, and both refusals name the scope
the gate chose — with no gate weakened.

**Independent Test**: run the three new/extended test modules plus the existing
gate suites; drive a move-task for a WP file that carries `pre_review_test_scope`
and observe the roster guard resolving and the head run executing the pinned
targets.

**Prompt**: `tasks/WP01-scope-key-budget-shape-and-diagnostics.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007,
FR-008, FR-009, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003

### Included Subtasks

T001 Red-first: WP-model + subtask-roster test for `pre_review_test_scope` (WP01)
T002 Red-first: review-budget shape-resolution test module (WP01)
T003 Red-first: refusal-diagnostic content test module (WP01)
T004 Declare `pre_review_test_scope` on `WPMetadata` (WP01)
T005 Whole-command budget default + `whole_command` selector (WP01)
T006 Wire the shape probe at the budget-resolution seam (WP01)
T007 Shape-aware refusal reasons (WP01)
T008 Docs, changelog fragment, targeted verification (WP01)

### Implementation Notes

- Test-first, in three slices: (1) the WP model/roster, (2) the budget shape,
  (3) the refusal text. Commit each RED slice before its fix.
- `WPMetadata` keeps `extra="forbid"`; the new field is additive and optional.
- The budget stays a single resolved number per transition. `whole_command` only
  selects the *default* when the project declares no `review.test_timeout_seconds`.
- The shape predicate is `not exposes_scope_breakdown(resolved source)`; the
  FR-004 override tier is always a bounded shape.
- Do not touch `gate_budget._RULES`, the block policy, or the retired census.

### Parallel Opportunities

- T002 and T003 are separate new test modules and can be authored in parallel
  with T001; the three fixes (T004–T007) are sequential because T006/T007 consume
  the shape vocabulary introduced by T005.

### Dependencies

- None (single package).

### Risks & Mitigations

- *Receipt mismatch*: capture, the receipt match and the head run must read the
  same memoised budget (FR-008). Mitigated by resolving only in
  `_mt_review_test_timeout` and asserting equality in a test.
- *Rendering churn*: the existing observability test pins the old reason wording;
  it is updated with paired whole-command/bounded assertions so the two shapes
  stay distinguishable (FR-006/FR-007).
- *Consumer surprise*: an undeclared-budget repo with a whole-suite command now
  gets 1,200 s instead of 300 s. Documented in `review-test-budget.md` and
  bounded by the unchanged 86,400 s ceiling; a declared value always wins
  (C-003).
