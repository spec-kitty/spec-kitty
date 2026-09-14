# Tasks: Blocked-WP unblock path (alloc-failure recovery) — #3937

**Mission**: `blocked-wp-unblock-path-01M29093` | **Branch**: `fix/3937-blocked-wp-unblock`
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Contract**: [contracts/blocked-recovery-behavior.md](./contracts/blocked-recovery-behavior.md)

Two independent work packages (disjoint files → parallel lanes, no inter-WP dependency).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED-first ATDD: alloc failure (DependencyLaneMergeConflict) leaves WP `planned`, no `planned→blocked` event; message carries `next_step` | WP01 | |
| T002 | RED-first ATDD: PlanningCommitMergeConflict path also stays `planned`; clean re-run leaves no `review-cycle://` pointer | WP01 | [P] |
| T003 | Implement: `implement.py` stops emitting blocked on alloc failure; prints `exc.next_step` for both conflict types | WP01 | |
| T004 | Validate WP01: targeted tests + mypy --strict + ruff green | WP01 | |
| T005 | RED-first ATDD: `blocked→planned` refusal identity = illegal-transition, enumerates `{in_progress, canceled}`, fake feedback file can't flip verdict; review-family rollback still requires feedback; start-impl reject names recovery | WP02 | |
| T006 | Implement: `_guard_planned_rollback` source-lane-scoped early-return (no `_GUARDS` reorder) | WP02 | |
| T007 | Implement: enumerate `allowed_targets()` on CLI/emit refusal path only (not FSM-core string); `work_package_lifecycle.py:256` reject names recovery | WP02 | |
| T008 | Validate WP02: targeted tests incl. `fsm_parity_baseline.jsonl` unchanged + mypy --strict + ruff green | WP02 | |

## Work Package 1 — F-50: allocation failure leaves the WP recoverable

- **Goal**: A workspace-allocation failure during `implement` leaves the WP in `planned` (no manufactured `blocked`) and prints the conflict's actionable `next_step`.
- **Priority**: P1 (core defect).
- **Independent test**: Drive `implement` against a conflicting dependency lane and a conflicting planning commit; assert the WP lane is unchanged `planned`, no `planned→blocked` event is emitted, and the printed output carries the exception's `next_step`.
- **Included subtasks**: T001, T002, T003, T004.
- **Files**: `src/specify_cli/cli/commands/implement.py`, `tests/integration/test_status_emit_on_alloc_failure.py`.
- **Dependencies**: none.
- **Requirements**: FR-001, FR-002, FR-003 (+ NFR-001, NFR-004).
- **Risks**: the one bug-encoding assertion at `test_status_emit_on_alloc_failure.py:189/192` must be rewritten (judge-the-test), not preserved. Prompt: `tasks/WP01-alloc-failure-leaves-planned.md` (~260 lines).

## Work Package 2 — F-51: honest single-stage transition refusal

- **Goal**: `move-task --to planned` out of a non-review lane (e.g. `blocked`) is refused as an illegal transition that names the legal targets, without demanding a fabricated review-feedback file; the "cannot start implementation" reject names the legal recovery.
- **Priority**: P1.
- **Independent test**: Request `blocked→planned`; assert refusal identity is illegal-transition (not feedback-demand), enumerates `{in_progress, canceled}`, and a fake `--review-feedback-file` cannot change the verdict; a review-family rollback still requires feedback.
- **Included subtasks**: T005, T006, T007, T008.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_transition_core.py`, `src/specify_cli/status/work_package_lifecycle.py`, `tests/status/test_transitions.py` (+ targeted move-task guard tests).
- **Dependencies**: none.
- **Requirements**: FR-004, FR-005, FR-006, FR-007 (+ NFR-001, NFR-002).
- **Risks**: must NOT touch the FSM-core illegal string (`wp_state.py:176/181`) — NFR-002; must NOT reorder `_GUARDS` (C-002). Prompt: `tasks/WP02-honest-transition-refusal.md` (~300 lines).

## MVP scope
WP01 alone delivers the core recoverability fix (F-50); WP02 completes the honest-refusal half (F-51).

## Post-review descope — WP02 not shipped (2026-09-14)

WP02 (F-51) was implemented and reviewed, then **cut before merge**. A KISS audit
asked for the cut on size grounds; a landing review then found a stronger reason,
and the stronger reason is the one that governs: **WP02 silently removed a
force-proof authorization gate.**

`_guard_planned_rollback` is the only thing standing between `move-task --to
planned` and the FSM, and its own refusal text promises "This requirement cannot
be bypassed with `--force`". WP02 turned that guard into a source-scoped
early-return keyed on `WPState.is_run_affecting` — which is `False` for
`genesis`, `blocked`, `done` and `canceled`. For those four sources the move then
fell through to the FSM, which **does** let `force` override an edge that does
not exist at all (`wp_state.py`: "Edge does not exist: only force … can
override"). And the force is often not the operator's: `done` is in
`_FORWARD_ORDER`, so FR-015 auto-force-promotion manufactures it.

Measured on the tree, WP02 restored vs. cut:

| `move-task --to planned` | flags | cut (shipped) | WP02 restored |
|---|---|---|---|
| from `done` | **none** | exit 1, stays `done` | exit 0, **back to `planned`** |
| from `blocked` | `--force` | exit 1, stays `blocked` | exit 0, back to `planned` |
| from `canceled` | `--force` | exit 1, stays `canceled` | exit 0, back to `planned` |
| from `genesis` | none | exit 1, stays `genesis` | exit 0, back to `planned` |
| from `blocked` | none | exit 1 *(message differs only)* | exit 1 |
| from `in_review` | either | exit 1, feedback demand | exit 1, unchanged |

Only the fifth row — no-force `blocked` — matches the "refused either way, only
the wording differs" reading, and that is the single row WP02's 292-line test
file covered: it passed `--force` nowhere and never used `done`, `canceled` or
`genesis` as a source. So a terminal, merged work package could be resurrected to
`planned` by a fat-fingered `move-task` with no flags, logged with a `force=true`
and a reason the operator never wrote.

**The F-51 concern is still legitimate, and its safe half is separable.**
`legal_targets_from()` and `_invalid_transition_diagnostic()` only enrich the
refusal *diagnostic* — they gate nothing, and they are safe to bring back. The
regression lived entirely in `_source_rolls_back_to_planned` and the
`_guard_planned_rollback` early-return. **Design constraint for whoever picks
F-51 up: keep `_guard_planned_rollback` unconditional; improve the message
without weakening the gate.** Tracked on the still-open #3937.
