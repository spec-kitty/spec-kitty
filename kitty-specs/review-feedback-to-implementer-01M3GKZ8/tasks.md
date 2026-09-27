# Work Packages: Rejection feedback reaches the implementer

**Inputs**: Design documents from `/kitty-specs/review-feedback-to-implementer-01M3GKZ8/`
**Prerequisites**: plan.md (required), spec.md (user stories), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Required. This mission is ATDD/red-first (NFR-002): each defect carries an issue-pinned
acceptance scenario that is demonstrably RED before the fix and green after. Every WP commits its
failing regression test(s) BEFORE the implementation change.

**Organization**: Fine-grained subtasks (`Txxx`) roll up into two work packages (`WPxx`) with
**disjoint file ownership**. WP01 owns the two write-side transition modules; WP02 owns the two
render-side workflow modules. `src/specify_cli/review/cycle.py` (and the rest of the feedback
grammar) is a FROZEN read-only dependency for both (NFR-001).

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/concerns).
- Subtasks are **reference rows**, not checkboxes: record completion with
  `spec-kitty agent tasks mark-status <Txxx> --status done`. The reduced event-log snapshot is the
  sole subtask-completion authority — there is no `- [ ]` box to tick.

## Path Conventions

- **Single project**: `src/specify_cli/`, `tests/`.

---

## Work Package WP01: Coupled rejection-feedback persistence on the re-implement edge (Priority: P1) 🎯 MVP

**Goal**: Make the `in_review → in_progress` (re-implement) rejection edge record reviewer feedback
identically to the `in_review → planned` edge, with the coupling enforced by ONE pure predicate so it
can never be half-fixed (#4899, C-003).
**Independent Test**: Reject an in-review WP onto the re-implement edge with feedback and inspect the
recorded review state — a committed review-cycle record exists, the feedback location is populated,
and the emitted `event.review_ref` resolves to feedback text equal, by value, to the reviewer's input;
compared field-for-field against the `in_review → planned` edge on a shared fixture. A no-rationale
re-implement rejection is refused (non-zero/abort).
**Prompt**: `/tasks/WP01-rejection-feedback-write-seam.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-008, NFR-002, NFR-003, C-003

### Included Subtasks

T001 [red-first] Commit failing SC-001 (parity record) + SC-002 (no-rationale refusal) scenarios in `tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py`, plus the `is_review_rejection_edge` truth-table + →planned/→in_progress parity in `tests/characterization/test_trio_pure_cores.py`
T002 Introduce the pure predicate `is_review_rejection_edge(old_lane, target_lane) -> bool` in `tasks_transition_core.py` (union semantics per frozen contract; ≤3 lines, no I/O)
T003 Route the five `== Lane.PLANNED` rejection-family sites (incl. `_mt_hop_review_result` at `tasks_move_task.py:2539`) through the predicate and generalize `Emit.planned_rollback → is_review_rejection`
T004 [P] Campsite tidy-first: extract `_mt_persist_rejection_cycle(st, ports)` from `tasks_move_task.py:2334-2348`; keep every touched function ≤15 complexity; add a focused unit test for the helper
T005 Conditional FR-008 (#3451): reproduce the review-cycle counter double-increment on the re-implement edge red-first; if it reproduces, fix increment-exactly-once with its own scenario; else record out-of-scope
T006 NFR-003 guard: prove arbiter-forward `in_review → {approved, done}` stays OUTSIDE the predicate; keep the existing arbiter-override coverage green (do NOT touch `is_arbiter_override` / `arb_review_ref`)
T007 Run the WP01 validation surface and record passed/failed counts in the PR *Tests run* section

### Implementation Notes

- Predicate contract is FROZEN in `contracts/is-review-rejection-edge.md`; WP02 consumes the signature.
- Union (`target == PLANNED` OR `old == IN_REVIEW and target == IN_PROGRESS`) is load-bearing: gates 1 & 4
  fire today for `* → planned` from ANY source; narrowing would regress that guard.
- Gate sites (verified @ current lines): gate1 `tasks_move_task.py:615`; gate2 persist-call
  `tasks_move_task.py:2334` (+ rebuild trigger `:2371`) via the renamed `Emit` flag set at
  `tasks_transition_core.py:829`; gate3 `tasks_transition_core.py:296`; gate4 `_guard_planned_rollback`
  `tasks_transition_core.py:595`.

### Parallel Opportunities

- T004 (helper extraction + its unit test) is `[P]` — behavior-preserving and independent of the gate wiring once the predicate (T002) exists.

### Dependencies

- None (foundation).

### Risks & Mitigations

- Regressing the any-source `→planned` guard → mitigated by the union predicate (T002) + T001 parity test.
- Regressing the arbiter-override moment (#4809/NFR-003) → predicate returns `False` for
  `in_review → {approved,done}` by construction; T006 keeps arbiter coverage green.
- Complexity ceiling (`tasks_move_task.py` ≈3670 lines, C901/S3776 ≤15) → T004 tidy-first extraction.

**Estimated prompt size**: ~430 lines.

---

## Work Package WP02: Render recorded feedback into the regenerated prompt — loudly, on both topologies (Priority: P1)

**Goal**: Ensure durably recorded rejection feedback renders into the regenerated fix-mode prompt on
BOTH single-branch and coordination topologies, and that a fix-mode generation failure surfaces a
visible warning instead of silently substituting a feedback-less prompt (#5024, FR-005/006/007).
**Independent Test**: With feedback persisted, regenerate the fix-mode prompt on a single-branch AND a
coordination-topology mission and confirm the feedback text appears in both; separately force fix-mode
generation to fail and confirm a visible warning surfaces with no silent feedback-less substitution.
**Prompt**: `/tasks/WP02-render-feedback-dual-topology.md`
**Requirement Refs**: FR-005, FR-006, FR-007, NFR-001, NFR-002

### Included Subtasks

T008 [red-first] In `tests/agent/test_workflow_review_cycle_pointer.py`: add a real coordination fixture proving SC-004's coord half is independently RED given a record already present, and a no-pre-seed end-to-end reject→render flow for SC-005 (the anti-mask control)
T009 Make the silent fall-through visible: `workflow_executor.py:1161-1163` (`except Exception: logger.warning(...); return None`) emits an operator-VISIBLE console warning naming the WP + cause before returning None; keep concrete recovery (no effect-free handler)
T010 Re-route the render feedback-context event-log read to `STATUS_STATE`: route `resolve_review_feedback_context` / `latest_review_feedback_reference` / `has_prior_rejection` (`workflow_cores.py:340/311/394`) through `placement_seam(...).read_dir(STATUS_STATE)`, mirroring `_resolve_verdict_read_feature_dir`; update `implement_resolve_feedback_and_gate` (`workflow_executor.py:667`); keep the review-cycle ARTIFACT read on `WORK_PACKAGE_TASK`
T011 [P] Add NEW test `tests/agent/test_build_implement_prompt_lines.py` for `build_implement_prompt_lines` (`workflow_executor.py:1302`) covering feedback-present and feedback-absent branches (SC-003 positive control + SC-005 render assertion)
T012 Single-branch non-regression: confirm PRIMARY == COORD == repo_root collapses the re-route to a no-op and single-branch render still passes
T013 Run the WP02 validation surface and record passed/failed counts in the PR *Tests run* section

### Implementation Notes

- Contract FROZEN in `contracts/render-feedback-contract.md`. Consumes from WP01/grammar:
  `is_review_rejection_edge(old_lane, target_lane) -> bool`, the emitted resolvable `review-cycle://…`
  pointer shape, and the frozen grammar predicates `is_non_resolvable_review_ref` /
  `is_synthetic_review_ref` + `ReviewCycleArtifact` (`review/cycle.py`, `review/artifacts.py` —
  READ-ONLY, NFR-001).
- F4 is RESOLVED as INDEPENDENT-RED: the coord render defect is not a downstream consequence of the
  write-side loss; T008 must PROVE it red on a real coord fixture with a record already present.

### Parallel Opportunities

- T011 (new `build_implement_prompt_lines` test) is `[P]` — an isolated pure-function test independent of T009/T010.

### Dependencies

- Depends on WP01. SC-005 (end-to-end, no pre-seeding) requires the write side to produce a resolvable
  record before the render can surface it.

### Risks & Mitigations

- The `STATUS_STATE` re-route must not break single-branch → single-branch collapses both partitions to
  `repo_root`, so the seam is a no-op there; T012 asserts it.
- Reading the wrong partition for the ARTIFACT → keep the review-cycle artifact read on
  `WORK_PACKAGE_TASK` (unchanged); only the event-log read moves to `STATUS_STATE`.

**Estimated prompt size**: ~400 lines.

---

## Dependency & Execution Summary

- **Sequence**: WP01 (write-side seam) → WP02 (render + dual-topology).
- **Parallelization**: Within each WP, the `[P]` subtasks (T004; T011) are safe to run alongside the
  rest of their package. Across WPs, WP02 must not start its end-to-end SC-005 assertion until WP01's
  resolvable record exists.
- **Disjoint ownership**: WP01 owns `tasks_transition_core.py` + `tasks_move_task.py`; WP02 owns
  `workflow_executor.py` + `workflow_cores.py`. No overlap; `review/cycle.py` is shared read-only.
- **MVP Scope**: WP01 is the structural root cause and the MVP — nothing downstream can surface feedback
  until the record is durably persisted with a resolvable reference.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| FR-004 | WP01 |
| FR-005 | WP02 |
| FR-006 | WP02 |
| FR-007 | WP02 |
| FR-008 | WP01 |
| NFR-001 | WP02 |
| NFR-002 | WP01, WP02 |
| NFR-003 | WP01 |
| C-003 | WP01 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Red-first parity + no-rationale + predicate truth-table scenarios | WP01 | P1 | No |
| T002 | Introduce `is_review_rejection_edge` pure predicate | WP01 | P1 | No |
| T003 | Route five rejection-family sites + generalize `Emit` flag through the predicate | WP01 | P1 | No |
| T004 | Tidy-first extract `_mt_persist_rejection_cycle` + unit test | WP01 | P1 | Yes |
| T005 | Conditional FR-008 (#3451) counter increment-exactly-once | WP01 | P2 | No |
| T006 | NFR-003 arbiter-override non-regression guard | WP01 | P1 | No |
| T007 | Run WP01 validation surface, record counts | WP01 | P1 | No |
| T008 | Red-first coord SC-004 + end-to-end SC-005 anti-mask scenarios | WP02 | P1 | No |
| T009 | Visible fall-through warning on fix-mode generation failure | WP02 | P1 | No |
| T010 | STATUS_STATE render event-log re-route (dual-topology) | WP02 | P1 | No |
| T011 | New `build_implement_prompt_lines` test | WP02 | P1 | Yes |
| T012 | Single-branch no-op / non-regression assertion | WP02 | P1 | No |
| T013 | Run WP02 validation surface, record counts | WP02 | P1 | No |

---

> Deep implementation detail lives in the per-WP prompt files under `/tasks/`. Keep this file as the
> high-level checklist; record subtask completion with `spec-kitty agent tasks mark-status`.
