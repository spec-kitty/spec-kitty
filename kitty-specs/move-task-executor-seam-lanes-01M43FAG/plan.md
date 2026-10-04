# Implementation Plan: Move-task executor seam and test-friction cleanup

**Branch**: `claude/move-task-degod-slice-2` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

This is slice 2 of #5629. The remaining decision, emission and recovery logic moves out of `tasks_move_task.py` into two sibling seam modules: `tasks_move_task_hops.py` for the pure hop builders and `tasks_move_task_executor.py` for planning, emission and recovery. The runtime-annotation emitter choice (owned checkout, then auto_commit, then plain) moves behind one coordination-shell helper that both move-task and mark-status call. Before any code moves, the move-task test surface is de-frictioned (DIRECTIVE_041 and the development-assist test-cleanup procedure), so that later moves need no hand edits to symbol lists:

- derive the compat keysets instead of listing them;
- generalise the no-shadow guard;
- retire the commit-hash provenance pin and the spent capture harness.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, the `specify_cli.status` transition pipeline, `specify_cli.coordination.status_transition`
**Testing**: pytest (+xdist `--dist loadfile`), the architectural gate battery
**Target Platform**: CLI
**Project Type**: single project
**Constraints**: verbatim moves (C-003); one authoritative validation (C-002); no gate-ledger widening (C-004)

## Charter Check

- **Single canonical authority.** The event log stays the sole authority. The shell helper removes the parallel emitter-choice authority in mark-status. PASS
- **Architectural alignment.** The new modules sit in the `specify_cli` adapter layer. The shell helper keeps the status→coordination import direction by importing lazily. PASS
- **ATDD / red-first (ADR 2026-07-17-1).** This is behaviour-preserving relocation with no defect to reproduce. New seams get focused tests in the same commit. N/A for red-first, PASS for tests.
- **Campsite / test remediation (DIRECTIVE_041, procedure development-assist-test-cleanup).** IC-01 and IC-05 apply them. PASS
- **Terminology.** "Mission" only, never "feature"; "status commit" is used where relevant. PASS

## Project Structure

### Documentation (this mission)

```
kitty-specs/move-task-executor-seam-lanes-01M43FAG/
├── spec.md  plan.md  tasks.md  tasks/WP0*.md
└── traces/ (tooling-friction.md, approach.md, design-decisions.md)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/
├── tasks_move_task.py            # CLI: parse, sequence, present (shrinks)
├── tasks_move_task_gates.py      # slice 1
├── tasks_move_task_hops.py       # NEW: pure hop builders
└── tasks_move_task_executor.py   # NEW: plan finalize, emit, persist, rollback, lock
src/specify_cli/coordination/status_transition.py   # NEW helper emit_runtime_annotation
src/specify_cli/cli/commands/agent/tasks_mark_status.py  # adopts the helper
tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py  # derived keysets
tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py  # generalised seam guard
tests/review/test_transition_gate_parity.py, tests/review/fixtures/parity/_capture.py
```

## Complexity Tracking

None. Every function keeps its current complexity, because the bodies move verbatim.

## Implementation Concern Map

### IC-01 — Test-friction pre-work

- **Purpose**: Make the compat guard and the seam guard derive their keysets from module definitions, so that moves need no hand-maintained lists.
- **Relevant requirements**: FR-005, FR-006
- **Affected surfaces**: `test_tasks_compat_surface.py`, `test_tasks_move_task_gates_seam.py` (generalised into `test_tasks_move_task_seams.py`)
- **Sequencing/depends-on**: none
- **Risks**: Losing the invariant that each `tasks.<name>` is the seam's object, not a copy. Keep the identity check and add a negative control.

### IC-02 — Hop-builder seam

- **Purpose**: Move the pure hop builders into `tasks_move_task_hops.py`.
- **Relevant requirements**: FR-001, FR-003
- **Affected surfaces**: `tasks_move_task.py`, the new hops module, tests patching `_mt_hop_review_result`
- **Sequencing/depends-on**: IC-01
- **Risks**: `_mt_hop_review_result` is patched on `tasks`, so the call site in `_mt_emit_transitions` must keep calling it through `_tasks.`.

### IC-03 — Executor seam

- **Purpose**: Move plan finalisation, emission, persistence, rollback and lock release into `tasks_move_task_executor.py`.
- **Relevant requirements**: FR-002, FR-003, FR-008
- **Affected surfaces**: `tasks_move_task.py`, the new executor module, the status-events writes gate allow-list, `untrusted_path_audit/inventory.md`, tests patching `_mt_finalize_plan` / `_mt_execute`
- **Sequencing/depends-on**: IC-02
- **Risks**: Patch interception (`_tasks.` bridge), gate allow-lists, import cycles.

### IC-04 — Shell-owned runtime-annotation emit

- **Purpose**: One helper, `emit_runtime_annotation(owned, auto_commit, ...)`, in `coordination/status_transition.py`, adopted by move-task and mark-status.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `coordination/status_transition.py`, `tasks_move_task_executor.py`, `tasks_mark_status.py`
- **Sequencing/depends-on**: IC-03
- **Risks**: The #3460 plain path must not build a transaction. `owned=` threading must be kept (#3866). Mark-status tests patch emitters on `tasks_mark_status`.

### IC-05 — Parity-oracle provenance retirement and patch-site gate

- **Purpose**: Retire the base-commit provenance test and `_capture.py`, and add a grep gate that keeps re-homed patches pointing at live names.
- **Relevant requirements**: FR-007, FR-008
- **Affected surfaces**: `tests/review/test_transition_gate_parity.py`, `tests/review/fixtures/parity/_capture.py`
- **Sequencing/depends-on**: none, but it lands last so the gate sees the final module layout
- **Risks**: Deleting real decision coverage. Only provenance and capture go; the fixtures and replay tests stay.
