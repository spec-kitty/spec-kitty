# Tasks: Local event-log retention

**Mission**: `local-event-log-retention-01M5ZCJP` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)
**Branch**: planning base and merge target `issue-6610-local-event-log-retention`

Three sequential work packages, one per implementation concern. WP01 is the MVP (#5212 on its own is shippable).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first ATDD tests for the per-surface cleanup policy | WP01 | |
| T002 | `RetentionRule`, `CleanupPolicy`, required `StateSurface.cleanup_policy`, `to_dict` | WP01 | |
| T003 | Classify all 62 registry surfaces | WP01 | |
| T004 | `surfaces_by_retention` helper; align existing contract/doctor tests | WP01 | |
| T005 | Tidy-first: expose `event_log_lock_path`, add `try_run_cursor_lock` | WP02 | |
| T006 | Red-first ATDD tests for limits and the retention engine (ADR D-3 Confirmation fixture) | WP02 | |
| T007 | `core/ledger_retention.py`: `RetentionLimits`, loader, `RetentionConfigError` | WP02 | |
| T008 | `state/retention.py` scan: policy-selected collectors, age, Mission resolution, verdicts | WP02 | |
| T009 | `state/retention.py` apply: locks, run-index entry removal, deletion, failures | WP02 | |
| T010 | Preview performance check over 1,000 runs | WP02 | [P] |
| T011 | Red-first CLI tests for `doctor event-logs` | WP03 | |
| T012 | `_event_logs_doctor.py`: self-registering subcommand, human + JSON report, exit codes | WP03 | |
| T013 | CLI reference block and any generated CLI surface snapshots | WP03 | |
| T014 | How-to page and changelog `[Unreleased]` entry | WP03 | [P] |

## WP01 — Per-surface cleanup policy (#5212)

**Prompt**: [tasks/WP01-per-surface-cleanup-policy.md](tasks/WP01-per-surface-cleanup-policy.md)
**Goal**: every `StateSurface` declares a required `CleanupPolicy`; invariants make the committed tier unprunable. **Priority**: P1. **Independent test**: `pytest tests/core/test_state_cleanup_policy.py`.
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-013.
**Dependencies**: none.

T001 Red-first ATDD tests for the per-surface cleanup policy (WP01)
T002 `RetentionRule`, `CleanupPolicy`, required `StateSurface.cleanup_policy`, `to_dict` (WP01)
T003 Classify all 62 registry surfaces (WP01)
T004 `surfaces_by_retention` helper; align existing contract/doctor tests (WP01)

**Sketch**: tests first (commit red) → types → classify → helper. **Risks**: misclassification (invariants catch the dangerous ones); exact-key assertions on `to_dict()` elsewhere.

## WP02 — Retention limits and engine (#6610)

**Prompt**: [tasks/WP02-retention-limits-and-engine.md](tasks/WP02-retention-limits-and-engine.md)
**Goal**: read `ledger.retention`, select surfaces from the registry policy, decide verdicts and delete safely. **Priority**: P1. **Independent test**: `pytest tests/core/test_ledger_retention.py tests/core/test_event_log_retention.py`.
**Requirements**: FR-005, FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, NFR-001, C-001, C-002.
**Dependencies**: WP01.

T005 Tidy-first: expose `event_log_lock_path`, add `try_run_cursor_lock` (WP02)
T006 Red-first ATDD tests for limits and the retention engine (WP02)
T007 `core/ledger_retention.py` (WP02)
T008 `state/retention.py` scan (WP02)
T009 `state/retention.py` apply (WP02)
T010 Preview performance check over 1,000 runs (WP02)

**Sketch**: behaviour-preserving accessor commit → red tests → limits → scan → apply → perf. **Risks**: lock order run → index; coord-topology Missions read as open (fail-safe); Windows open handles.

## WP03 — `doctor event-logs` command and docs (#6610)

**Prompt**: [tasks/WP03-doctor-event-logs-command.md](tasks/WP03-doctor-event-logs-command.md)
**Goal**: dry-run-first doctor subcommand with human and JSON reports; CLI reference, how-to and changelog. **Priority**: P1. **Independent test**: `pytest tests/cli/commands/test_doctor_event_logs.py`.
**Requirements**: FR-006, FR-012, C-003, C-004.
**Dependencies**: WP02.

T011 Red-first CLI tests for `doctor event-logs` (WP03)
T012 `_event_logs_doctor.py` (WP03)
T013 CLI reference block and generated CLI surface snapshots (WP03)
T014 How-to page and changelog `[Unreleased]` entry (WP03)

**Sketch**: red CLI tests → command → reference/snapshots → docs. **Risks**: `test_docs_cli_reference_parity.py`; completion-manifest freshness gate.

## Parallelization

Sequential by dependency (WP01 → WP02 → WP03). Within WP02, T010 can be written alongside T009; within WP03, T014 alongside T013.
