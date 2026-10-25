---
work_package_id: WP05
title: Multi-log writes gate and docs
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-005
- FR-006
- NFR-004
planning_base_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
merge_target_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
branch_strategy: Planning artifacts for this mission were generated on issue-6603-6606-eventbridge-gate-and-locked-appends. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6603-6606-eventbridge-gate-and-locked-appends unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
history:
- at: '2026-10-25T17:30:00Z'
  actor: claude
  note: Created by /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_event_log_writes_gate.py
execution_mode: code_change
owned_files:
- tests/architectural/test_event_log_writes_gate.py
- docs/architecture/event-ledger-writers-and-readers.md
- docs/development/reference/events-in-core.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
tracker_refs: []
---

# WP05: Multi-log writes gate and docs

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`architect-alphonso`) before reading anything else, then run `spec-kitty charter context --action implement`.

## Branch Strategy

Planning base and merge target: `issue-6603-6606-eventbridge-gate-and-locked-appends`. Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP05 --agent claude --mission eventbridge-gate-and-locked-appends-01M5T0TN`. Never choose a base branch by hand.

## Objective

FR-005, FR-006, NFR-004 and the docs. This is ADR 2026-10-14-1's Confirmation gate, as amended (the Python side of the two-gate proof).

## Subtasks

### T017 — `tests/architectural/test_event_log_writes_gate.py`

- Reuse `scan_write_sites` and `module_name_for` from `test_status_events_writes_gate.py`, importing only non-test names.
- Name the logs: `run.events.jsonl`, `decisions.events.jsonl`, `mission-events.jsonl`, `canonical-events.jsonl`, the glossary `*.events.jsonl` (not `status.events.jsonl`), the kitty-ops `lifecycle.jsonl`, `propagation-errors.jsonl`, `ops-index.jsonl` and `op-closures.jsonl`, plus `policy-audit.jsonl`, `archived-missions.jsonl`, `global.jsonl` and `.encoding-provenance.jsonl`.
- Freeze three ledgers:
  - **Door callers:** every call of `append_ledger_lines`, `ledger_lock` or `persistence.append_event` (any alias), keyed `(module, path expression)` with a count. Every entry is marked `#6193`, so a new caller fails.
  - **Raw writes:** a resolved path that is a named log, or any `.jsonl`, outside `kernel.ledger_append` and `specify_cli.status.store`. Ledgered with reasons: migrations, merge drivers, the exclusive Op create, glossary repair. A new one fails.
  - **Unresolved writes:** an unresolved path whose expression is ledger-named (`events`, `jsonl`, `ledger`, `log`) is pinned.
- Live checks for every ledger entry; synthetic non-vacuity floors for each log and each door shape; a floor that the real tree has at least 10 door callers.

### T018 — The doors call the port

AST pin: `_persist_prepared` and `BookkeepingTransaction.append_events` call `record_work_package_transition`, and name neither `append_event_stream_atomic_verified` nor `append_event_stream_log`.

### T019 — Docs

- `docs/architecture/event-ledger-writers-and-readers.md`:
  - writer rows show "Yes" for the lock;
  - G-1 and G-2 are partly closed and G-5 closed (with this Mission);
  - the lock contract is cited.
- `docs/development/reference/events-in-core.md`: a section "Appending to an event log (interim)" covering the lock contract, the door, the gate and its retirement at #6193.
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: an entry per the docs/changelog convention.
- Run `scripts/docs/check_changelog_style` and `tests/architectural/test_no_legacy_terminology.py`.
