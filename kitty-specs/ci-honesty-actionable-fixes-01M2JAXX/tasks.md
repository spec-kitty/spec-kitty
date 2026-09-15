# Tasks: CI Pipeline Honesty — Actionable Fixes

**Mission**: ci-honesty-actionable-fixes-01M2JAXX · **Branch**: `fix/ci-honesty-actionable-fixes`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Base for RED evidence**: `36d866d4fa`

Three work packages, each RED-first (the ATDD test is committed first, red on base, green on the
fix). Surfaces are disjoint → three independent lanes. #4454 and #4208 are consolidated into WP02
because both edit `.github/workflows/ci-router.yml` (keeping `owned_files` disjoint across WPs and
the two router edits in one worktree).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED: pin reconciler contracts C-recon-1..4 in tests/ci/test_reconcile_shards.py | WP01 | |
| T002 | Extract inline reconciler (ci-aggregate.yml:236-383) → scripts/ci/reconcile_shards.py (behaviour-preserving) | WP01 | |
| T003 | Invert completeness: selected-fresh required; unselected backfill-if-available, never fatal; preserve must_be_fresh | WP01 | |
| T004 | Wire ci-aggregate.yml to import/call reconcile(); keep fail-closed guard (:376-381) | WP01 | |
| T005 | Verify red→green + tests/ci + arch battery + ruff/mypy | WP01 | |
| T006 | RED: pin tests-only-selects-owning-module in test_gate_selection_authority.py (#4454) | WP02 | [P] |
| T007 | Add tests/<module>/** + tests/ci/** globs to router filter groups (same groups as src); watch no-duplicate-suite | WP02 | |
| T008 | RED: pin timed_out-distinct + blocking-unchanged in test_dual_mode_contract.py (#4208) | WP02 | [P] |
| T009 | Extract scripts/ci/router_gate.py classifier (reuse fleet_verdict conclusion vocab); wire router-gate step | WP02 | |
| T010 | Verify red→green for both #4454 & #4208 + arch battery + ruff/mypy | WP02 | |
| T011 | RED: pin nightly-suite-steps-are-fail-loud in test_performance_marker_guard.py (#4212) | WP03 | |
| T012 | Capture each suite exit code (perf/e2e/interpreter) into $GITHUB_ENV; keep annotations + run-all | WP03 | |
| T013 | Add terminal if:always() fail-loud step per job (performance-and-e2e, interpreter-matrix) | WP03 | |
| T014 | Verify red→green + run-all guards coexist + ruff/mypy | WP03 | |

*Reference rows — completion recorded via `spec-kitty agent tasks mark-status Txxx --status done`, not checkboxes.*

---

## WP01 — #4360-B: diff-scoped shard reconciler

- **Goal**: A diff-scoped PR whose selected shards all pass is reported complete; no false-red.
- **Priority**: P1 · **Requirements**: FR-001, FR-002, FR-003 (+ NFR-001/002/003)
- **Independent test**: `pytest tests/ci/test_reconcile_shards.py` (RED on base → GREEN on fix).
- **Included subtasks**: T001, T002, T003, T004, T005
- **Implementation sketch**: RED test first → extract reconciler behaviour-preserving → invert
  completeness with `must_be_fresh` preserved → wire the aggregate step → verify.
- **Dependencies**: none · **Risk**: over-relaxation → false-green (mitigated by T001 guard test C-recon-2).
- **Prompt**: [tasks/WP01-shard-reconciler.md](./tasks/WP01-shard-reconciler.md) (~5 subtasks)

## WP02 — #4454 + #4208: ci-router.yml honesty (routing + gate classification)

- **Goal**: A tests-only change runs its own tests (#4454); a timeout-kill is reported distinctly
  from an external cancel (#4208), blocking policy unchanged.
- **Priority**: P1/P2 · **Requirements**: FR-004, FR-005 (+ NFR-001/002/003)
- **Independent test**: `pytest tests/architectural/test_gate_selection_authority.py test_dual_mode_contract.py`.
- **Included subtasks**: T006, T007, T008, T009, T010
- **Implementation sketch**: two RED tests → add router filter globs (#4454) → extract + wire
  timed_out-aware classifier (#4208) → verify both, watch `test_no_duplicate_suite_execution`.
- **Dependencies**: none · **Risk**: overlapping router edits (mitigated: single WP owns ci-router.yml).
- **Prompt**: [tasks/WP02-router-honesty.md](./tasks/WP02-router-honesty.md) (~5 subtasks)

## WP03 — #4212: nightly fail-loud

- **Goal**: A nightly with a failing suite reports the job as failed, every suite still runs.
- **Priority**: P2 · **Requirements**: FR-006 (+ NFR-001/002/003)
- **Independent test**: `pytest tests/architectural/test_performance_marker_guard.py`.
- **Included subtasks**: T011, T012, T013, T014
- **Implementation sketch**: RED test → capture suite exit codes → terminal fail-loud step →
  verify run-all guards coexist.
- **Dependencies**: none · **Risk**: LOW (nightly-only, off the per-PR path).
- **Prompt**: [tasks/WP03-nightly-fail-loud.md](./tasks/WP03-nightly-fail-loud.md) (~4 subtasks)

---

## MVP scope

WP01 (#4360-B) is the highest-value MVP — it fixes the live-biting false-red on real PRs.

## Parallelization

All three WPs are independent (disjoint surfaces) and can run in parallel lanes. Within WP02, the
two RED tests (T006, T008) are `[P]`.
