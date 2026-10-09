# Tasks: Serialise concurrent next advance

Mission: `serialise-next-advance-01M4EF16` · Closes #5854, #5682.
Branch: `issue-5854-serialise-next`. Planning artifacts only; worktrees are
allocated per lane after `finalize-tasks`.

> Subtask rows below are reference rows, not checkboxes. Completion is
> event-sourced — record it with `spec-kitty agent tasks mark-status Txxx --status done`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first engine + lock tests (unique-temp collision pair; held-lock-blocks commit; commit_advance expected-step CAS unit; provide_decision_answer-under-lock) | WP01 | |
| T002 | Red-first bridge/e2e tests + invert the fallback pin (#5682 composition-window, #5854 engine-path, answer-vs-next, true-concurrency barrier `stress`; invert `test_pre_resolution_is_not_reused_for_a_different_issued_step` to assert `blocked` + 0 `next_step` calls) | WP01 | |
| T003 | Add `src/runtime/next/run_lock.py` (dedicated per-run-dir lock path + `machine_file_lock`, `run_index`-style) | WP01 | |
| T004 | `_write_snapshot` unique staging temp via `kernel.atomic` | WP01 | |
| T005 | Expected-step CAS: thread the bootstrap `issued_step_id` into `plan_advance`/`commit_advance` (widen `StaleAdvancePlan`) and through `runtime_bridge` + `runtime_bridge_engine`, both paths | WP01 | |
| T006 | Lock the commit RMW: wrap `_commit_advance`, `provide_decision_answer`, and the retrospective-rollback writer with the run-cursor lock | WP01 | |
| T007 | `_dn_advance_engine` refuses a stale plan (`blocked` + reason) and catches `LockAcquireTimeout`; remove the `next_step` fallback | WP01 | |
| T008 | Green: red→green on all repros, half-by-half revert checks, blast-radius tests, ruff/format/mypy/complexity; append tracer entries | WP01 | |
| T009 | Write the 4.x ADR for the run-dir writer model (cross-ref ADR `2026-02-17-1`; cite the run-index lock as same-primitive precedent) | WP02 | |
| T010 | Update `docs/architecture/runtime-loop.md` to state the serialisation guarantee | WP02 | [P] |
| T011 | Add a CHANGELOG `[Unreleased]` entry | WP02 | [P] |

## Work Packages

### WP01 — Serialise the run-cursor advance (lock + CAS + engine/bridge refusal)

- **Goal**: Close #5854 + #5682 by construction: an expected-step compare-and-swap
  folded into `commit_advance`'s `StaleAdvancePlan`, a short per-run-dir lock around
  the commit read-modify-write (covering `provide_decision_answer` and the
  retrospective-rollback writer), a unique snapshot temp, and an engine path that
  refuses a stale plan instead of re-planning `success`.
- **Priority**: P1. **Independent test**: the deterministic repros (red-first) in
  `quickstart.md`, plus the half-by-half revert checks (SC-003).
- **Subtasks**: T001, T002, T003, T004, T005, T006, T007, T008 (8).
- **Implementation sketch**: write the red-first tests (T001, T002) → add the lock
  helper (T003) and unique temp (T004) → the CAS (T005) → wrap the commit writers
  (T006) → the engine refusal (T007) → green + quality (T008).
- **Dependencies**: none. **Risks**: keep the lock span off the executor (NFR-001);
  no deadlock with the run-index lock (C-002); the rollback writer is deleted by the
  unmerged sibling `issue-5883-*` — cover it on current main.
- **Estimated prompt size**: ~450 lines.

### WP02 — ADR + docs for the run-dir writer model

- **Goal**: Record the cross-process run-dir writer model as a decision record and
  state the shipped guarantee where the multi-agent loop is advertised; add a
  changelog entry.
- **Priority**: P2. **Independent test**: ADR present and well-formed; the
  runtime-loop doc names the guarantee; changelog style gate passes.
- **Subtasks**: T009, T010, T011 (3).
- **Dependencies**: WP01 (documents the shipped behavior). **Risks**: keep the ADR
  short; cross-reference the existing contract ADR.
- **Estimated prompt size**: ~150 lines.

## Dependencies

- WP01: none.
- WP02: Depends on WP01.

## MVP

WP01 is the MVP: it delivers the entire behavioral fix and its acceptance gate.
WP02 is the governance/doc record that lands with it.
