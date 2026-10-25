---
work_package_id: WP04
title: EventBridge port behind the two transition doors
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- C-001
- C-004
- C-005
planning_base_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
merge_target_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
branch_strategy: Planning artifacts for this mission were generated on issue-6603-6606-eventbridge-gate-and-locked-appends. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6603-6606-eventbridge-gate-and-locked-appends unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
history:
- at: '2026-10-25T17:30:00Z'
  actor: claude
  note: Created by /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: src/runtime/next/
create_intent:
- src/runtime/next/event_bridge.py
- src/specify_cli/events/event_bridge.py
- tests/specify_cli/events/test_event_bridge.py
execution_mode: code_change
owned_files:
- src/runtime/next/event_bridge.py
- src/specify_cli/events/event_bridge.py
- src/specify_cli/status/emit.py
- src/specify_cli/coordination/transaction.py
- src/specify_cli/status/_unsafe.py
- tests/architectural/test_status_unsafe_allowlist.py
- tests/specify_cli/events/test_event_bridge.py
role: implementer
tags: []
tracker_refs: []
---

# WP04: EventBridge port behind the two transition doors

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`architect-alphonso`) before reading anything else, then run `spec-kitty charter context --action implement`.

## Branch Strategy

Planning base and merge target: `issue-6603-6606-eventbridge-gate-and-locked-appends`. Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP04 --agent claude --mission eventbridge-gate-and-locked-appends-01M5T0TN`. Never choose a base branch by hand.

## Objective

FR-001 to FR-004 (contract `contracts/event-bridge-port.md`). ADR 2026-10-14-1 D-2 and open question 6: the work package transition goes through the port, behind its two existing doors. There is no behaviour change and no transport (C-001).

## Subtasks

### T012 — `src/runtime/next/event_bridge.py`

- `TransitionRow(Protocol)`: `event_id`, `to_dict()`.
- `WorkPackageTransition`: a frozen dataclass with `write_location: Path`, `rows: tuple[TransitionRow, ...]` (non-empty, checked in `__post_init__`) and `write_contract: object | None`.
- `WorkPackageTransitionPort(Protocol)`: `record_work_package_transition(transition) -> None`.
- `EventBridgePort(RuntimeEventEmitter, WorkPackageTransitionPort, Protocol)`.
- A binding registry: `bind_work_package_transition_port`, `bound_work_package_transition_port`, `reset_work_package_transition_port`. Reject-on-conflict by `module.qualname` of `type(port)`; the same class rebinds.
- No `specify_cli` import beyond what `_internal_runtime.events` already brings (no new runtime outbound ledger entry).

### T013 — `src/specify_cli/events/event_bridge.py`

- `LocalFileEventBridge.record_work_package_transition`:
  - It checks that every row is a `StatusEvent` or an `InnerStateChanged` (otherwise `TypeError`).
  - It uses the coordination wrapper `append_event_stream_log(contract, rows)` when `write_contract` is an `EventLogWriteContract`.
  - With `None`, it uses `store.append_event_stream_atomic_verified(write_location, rows)`.
  - Lazy imports avoid cycles.
- `work_package_transition_port() -> WorkPackageTransitionPort`: the bound port, or a module-level `LocalFileEventBridge`.
- Docstring: the adapter becomes the write-service client at #6675/#6193.

### T014 — Flat shell

In `status/emit.py::_persist_prepared`, replace the direct store call with `work_package_transition_port().record_work_package_transition(WorkPackageTransition(feature_dir, (event, *annotation)))`. Materialize and mirror stay where they are.

### T015 — Coordination shell

In `BookkeepingTransaction.append_events`, replace `append_event_stream_log(write_contract, events)` with the port call carrying `write_contract`. The prune-on-failure path is unchanged.

### T016 — Tests and allowlist

`tests/specify_cli/events/test_event_bridge.py`:
- A recording port bound and called once per transition from each door, using real `emit_status_transition` / `emit_status_transition_transactional` fixtures from the existing status tests.
- The unbound path matches today's bytes.
- A conflicting binding raises; the same class rebinds.
- A row of the wrong type raises.
- An empty unit raises.
- A stub satisfying `EventBridgePort` type-checks.

Add `specify_cli.events.event_bridge` to `ALLOWED_CALLERS` (and the test baseline) with the comment: "EventBridge local file adapter (#6603, ADR 2026-10-14-1 D-1): the work package transition door both shells share; the primitives become private to it".

## Definition of Done

`tests/status`, `tests/specify_cli/status`, `tests/coordination`, `tests/specify_cli/coordination`, `tests/runtime`, and the architectural gates `test_status_unsafe_allowlist.py`, `test_status_events_writes_gate.py`, `test_layer_rules.py`, `test_runtime_emitter_seam.py` and `test_status_module_boundary.py` are green.
