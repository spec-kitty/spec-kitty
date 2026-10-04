# Work Packages: Move-task executor seam and test-friction cleanup

**Inputs**: `kitty-specs/move-task-executor-seam-lanes-01M43FAG/` (spec.md, plan.md)

Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

---

## Work Package WP01: Derived compat keysets and generalised seam guard (Priority: P0)

**Goal**: Stop hand-maintained symbol lists from turning the suite red on behaviour-neutral moves.
**Independent Test**: `pytest tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py tests/specify_cli/cli/commands/agent/test_tasks_move_task_seams.py` is green. A negative control (a planted shadow copy) fails the guard.
**Prompt**: `/tasks/WP01-derived-compat-keysets.md`
**Requirement Refs**: FR-005, FR-006

### Included Subtasks

T001 Derive the per-seam keysets in `test_tasks_compat_surface.py` from native module definitions; drop the hand-listed tuples and count-ratchet comments
T002 Generalise `test_tasks_move_task_gates_seam.py` into a parametrised `test_tasks_move_task_seams.py` covering every move-task seam module
T003 Add a negative-control test proving the identity guard catches a shadow copy

### Dependencies

- None.

---

## Work Package WP02: Shell-owned runtime-annotation emit (Priority: P1)

**Goal**: One coordination-shell helper picks the inner-state emitter (owned → transactional with `owned=`; auto_commit → transactional; else plain). mark-status adopts it.
**Independent Test**: The helper unit tests pin all three branches; mark-status tests pass unchanged.
**Prompt**: `/tasks/WP02-shell-runtime-annotation-emit.md`
**Requirement Refs**: FR-004, C-001

### Included Subtasks

T004 Add `emit_runtime_annotation(...)` to `coordination/status_transition.py` with lazy imports
T005 Adopt it in `tasks_mark_status.py` (owned branch only, which is equivalent to auto_commit=False)
T006 Unit tests: three branches, the plain branch builds no transaction (#3460), `owned=` threaded (#3866)

### Dependencies

- None.

---

## Work Package WP03: Hop and executor seam modules (Priority: P1)

**Goal**: Move the hop builders and the planning/emission/recovery family VERBATIM into `tasks_move_task_hops.py` and `tasks_move_task_executor.py`. The executor adopts the WP02 helper.
**Independent Test**: The move-task / review / status suites pass; `tasks_move_task.py` is at most 2,050 LOC; the `validate_transition(` grep count is unchanged.
**Prompt**: `/tasks/WP03-hop-and-executor-seams.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-008, NFR-001, NFR-002, NFR-003, C-002, C-003, C-004

### Included Subtasks

T007 Move the hop builders to `tasks_move_task_hops.py` with identity re-exports
T008 Move the executor family to `tasks_move_task_executor.py` with identity re-exports and the `_tasks.` bridge preserved
T009 `_mt_emit_runtime_state` delegates its emitter choice to `emit_runtime_annotation`
T010 Re-home intercepting patch sites; update the architectural gate entries (no widening)

### Dependencies

- Depends on WP01, WP02.

---

## Work Package WP04: Parity-oracle provenance retirement and patch-site gate (Priority: P2)

**Goal**: Retire the commit-hash provenance pin and the spent capture harness, and add a gate keeping test patch targets live.
**Independent Test**: `pytest tests/review/test_transition_gate_parity.py tests/specify_cli/cli/commands/agent/test_move_task_patch_targets_live.py` is green.
**Prompt**: `/tasks/WP04-parity-provenance-and-patch-gate.md`
**Requirement Refs**: FR-007, FR-008

### Included Subtasks

T011 Retire `test_fixture_provenance_is_machine_emitted_base_commit` and `tests/review/fixtures/parity/_capture.py`; re-point any references
T012 Add the patch-target liveness gate: every `patch.object`/`monkeypatch.setattr` on a move-task seam module names an attribute that the module defines natively or calls

### Dependencies

- Depends on WP03.
