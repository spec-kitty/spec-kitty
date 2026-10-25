---
work_package_id: WP02
title: Route the eight G-5 writers and the glossary append
dependencies:
- WP01
requirement_refs:
- FR-008
- FR-010
- NFR-001
planning_base_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
merge_target_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
branch_strategy: Planning artifacts for this mission were generated on issue-6603-6606-eventbridge-gate-and-locked-appends. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6603-6606-eventbridge-gate-and-locked-appends unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-eventbridge-gate-and-locked-appends-01M5T0TN
base_commit: 03da4bcad20b4018f29f4cf3ef18d21d68ac1b2c
created_at: '2026-10-25T18:22:11.018212+00:00'
subtasks:
- T005
- T006
- T007
- T008
history:
- at: '2026-10-25T17:30:00Z'
  actor: claude
  note: Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- src/runtime/next/next_invocation_lifecycle.py
- tests/specify_cli/invocation/test_locked_lifecycle_and_propagation.py
- tests/specify_cli/events/test_decision_log_locked_append.py
- tests/specify_cli/mission_v1/test_events_locked_append.py
- tests/runtime/test_run_journal_locked_append.py
- tests/policy/test_audit_locked_append.py
- tests/missions/test_archive_locked_append.py
- tests/charter/test_encoding_provenance_locked_append.py
- tests/glossary/test_events_locked_append.py
- tests/runtime/test_run_state_hardening.py
- tests/specify_cli/invocation/test_propagator.py
execution_mode: code_change
owned_files:
- src/specify_cli/invocation/lifecycle.py
- src/specify_cli/invocation/propagator.py
- src/specify_cli/events/decision_log.py
- src/specify_cli/mission_v1/events.py
- src/runtime/next/_internal_runtime/engine.py
- src/specify_cli/policy/audit.py
- src/specify_cli/missions/_archive.py
- src/charter/activation/_io.py
- src/glossary/events.py
- src/runtime/next/next_invocation_lifecycle.py
- tests/specify_cli/invocation/test_locked_lifecycle_and_propagation.py
- tests/specify_cli/events/test_decision_log_locked_append.py
- tests/specify_cli/mission_v1/test_events_locked_append.py
- tests/runtime/test_run_journal_locked_append.py
- tests/policy/test_audit_locked_append.py
- tests/missions/test_archive_locked_append.py
- tests/charter/test_encoding_provenance_locked_append.py
- tests/glossary/test_events_locked_append.py
- tests/runtime/test_run_state_hardening.py
- tests/specify_cli/invocation/test_propagator.py
role: implementer
tags: []
tracker_refs: []
---

# WP02: Route the eight G-5 writers and the glossary append

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`) before reading anything else, then run `spec-kitty charter context --action implement`.

## Branch Strategy

Planning base and merge target: `issue-6603-6606-eventbridge-gate-and-locked-appends`. Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP02 --agent claude --mission eventbridge-gate-and-locked-appends-01M5T0TN`. Never choose a base branch by hand.

## Objective

FR-008, FR-010, NFR-001: the eight G-5 sites and the glossary contract append take the interim ledger lock. Bytes are unchanged.

## Subtasks

### T005 — Red-first

One test file per owning module (paths in `owned_files`; the tree mirrors the source):
- Seed the target log with a torn tail (`b'{"x":1'`).
- Call the writer's public entry: `append_lifecycle_record`, `_log_propagation_error`, `DecisionGitLog._append_to_file`, `mission_v1.events._write_event`, `engine._append_event`, `append_audit_event`, `append_archive_record`, `_write_provenance`.
- Assert the file is byte-identical. For writers that swallow, assert no exception and the file unchanged; for writers that raise, assert `EventLogTornTailError`.

Also add one byte-stability case per writer (a clean log → the expected exact line). Run it before routing: the torn-tail cases are RED and the byte cases are green. Record the counts.

### T006 — invocation, decision log, Mission v1

Each site replaces the `open("a")` block with `append_event_log_lines(path, [line_without_newline], create_parents=<as today>)`.
- `lifecycle.py` already does `mkdir`, so pass `create_parents=True` and drop the explicit mkdir.
- `propagator.py` mkdirs: `create_parents=True`, and keeps catching `Exception`.
- `decision_log.py` keeps its compact separators and keeps `mkdir`.
- `mission_v1/events.py` does not mkdir today: `create_parents=False`.
- Each site gets the comment `# interim-locked-append: retires at the #6193 handover`.

### T007 — runtime, policy, archive, provenance

- `engine.py`: `create_parents=False`, as today. `fsync` is now done by the primitive. Keep `canonical-producer-exempt: #1248` and update the comment: the journal is locked now, no longer "single-writer by assumption".
- `audit.py`: `create_parents=False`.
- `_archive.py`: `create_parents=True`.
- `charter/activation/_io.py`: `create_parents=True`, and keep the `OSError` warning, which now also covers the refusal.

### T008 — Glossary

`glossary/events.py::append_event` runs its library append, torn-tail repair and retry inside `event_log_lock(event_log_path)`. The repair's own sibling lock stays (it is inert under the outer lock). The docstring says the append is locked now, so the advisory torn-tail check is no longer racy.

### T008b — Fold the review findings

- `next_invocation_lifecycle.py::_pair_previous_lifecycle_record` catches `EventLogAppendError` around `write_paired_completion`, logs a warning and continues, as the issuance path already does with `OSError`. Test it.
- `tests/runtime/test_run_state_hardening.py:362-383` patches `os.fsync` process-wide, which the lock record write also calls. Narrow the patch to the journal fd, or assert through the primitive.
- `tests/specify_cli/invocation/test_propagator.py:242` patches `builtins.open`. Re-point it at the primitive so it is not vacuous.

## Definition of Done

T005 is green after routing. The writers' existing suites pass: `tests/specify_cli/invocation`, `tests/runtime`, `tests/next`, `tests/specify_cli/policy`, `tests/missions`, `tests/charter`, `tests/glossary`, plus `grep -rl` for each module.
