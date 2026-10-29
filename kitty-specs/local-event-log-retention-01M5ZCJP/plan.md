# Implementation Plan: Local event-log retention

**Branch**: `issue-6610-local-event-log-retention` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/local-event-log-retention-01M5ZCJP/spec.md`

## Summary

Add a required `CleanupPolicy` (retention rule + cleanup command) to every `StateSurface` in the state registry (#5212), then add `spec-kitty doctor event-logs [--apply] [--json]` (#6610). The command reads its scope only from the registry: surfaces whose rule is `ledger_retention` are judged against `ledger.retention` limits and Mission completion; surfaces whose rule is `rebuildable` are always candidates unless locked. It previews by default and deletes only with `--apply`, holding the same OS lock a writer of that item takes, and removes a deleted run's run-index entry under the index lock. Grounding and decisions: [research.md](research.md).

## Engineering Alignment

Taken autonomously inside the confirmed scope (mechanics only; every operator decision is recorded in research.md §5):

- **Module placement.** Policy types live beside `StateSurface` in `src/specify_cli/state/contract.py`. Limits are read by a new `src/specify_cli/core/ledger_retention.py`, a sibling of `core/ledger_posture.py` (the existing `ledger.*` reader). The retention engine is `src/specify_cli/state/retention.py` (pure scan/plan + apply). The CLI shell is a self-registering doctor sibling, `src/specify_cli/cli/commands/_event_logs_doctor.py`; `doctor.py` is not edited (C-003).
- **Locks.** No event-log door is called (C-001). The engine probes and holds the OS locks through `kernel.locks.machine_file_lock(..., blocking=False)` on: the run-cursor lock (`runtime.next.run_lock`, new public non-blocking accessor) for a run; the event-log lock path (`kernel.event_log_append.event_log_lock_path`, added to `__all__`) for a glossary log and the Op index cache. Lock files are never deleted on their own.
- **Lock order for a run.** Run-cursor lock (non-blocking) → run-index lock (`index_lock`, bounded blocking) → drop index entries → remove the run directory → release. No path holds the index lock and then waits on a run lock (C-002 in `run_lock.py` keeps them un-nested everywhere else), so this one-way nesting cannot deadlock; it is documented at the call site.
- **Age.** The newest modification time of the item's files (run directory: every file in it; log/cache: the file). Rationale and alternative in research.md §7.
- **Mission resolution.** Run: `mission_slug` from `state.json` → `kitty-specs/<slug>/`, else `mission_id` matched against `kitty-specs/*/meta.json`. Glossary log: the filename stem matched against the sanitized `mission_id` of each Mission. Completion: `status.lifecycle.is_mission_completed`, evaluated lazily (only for items already outside both limits) and memoized per Mission.
- **Config errors fail closed.** An invalid `ledger.retention` value raises before any scan; the command exits 2 in both modes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (existing); no new dependency (supply-chain check: nothing to examine — no dependency added, upgraded or removed)
**Storage**: Files under `.kittify/` and `kitty-ops/` (gitignored local tier only)
**Testing**: pytest, red-first per WP; `tests/specify_cli/test_state_contract.py`, new `tests/specify_cli/state/test_retention*.py`, `tests/specify_cli/core/test_ledger_retention.py`, `tests/specify_cli/cli/commands/test_event_logs_doctor.py`; named gates `tests/architectural/test_event_log_writes_gate.py`, `test_docs_cli_reference_parity.py`, `test_lock_primitive_ban.py`, `test_no_dead_symbols.py`
**Target Platform**: Linux, macOS, Windows 10+ (locks via the kernel primitive, which covers `msvcrt`)
**Project Type**: single (CLI)
**Performance Goals**: preview over 1,000 runs < 2 s (NFR-001)
**Constraints**: no new event-log writer or door caller; committed tier untouched; complexity ≤ 15; diff coverage ≥ 90%
**Scale/Scope**: 62 registry surfaces; ~4 new/changed source modules

## Charter Check

| Gate | Status |
|---|---|
| Single canonical authority | Pass — the registry policy is the only scope source; FR-013 pins it. Retention limits read only from `.kittify/config.yaml` `ledger.retention` (ADR D-3). |
| Architectural alignment | Pass — `specify_cli → runtime/kernel` import direction respected; ADR 2026-10-22-1 adds no writer. |
| ATDD-first | Pass — each WP opens with a failing acceptance test commit. |
| Terminology canon | Pass — Mission, never feature, in new prose and identifiers (existing `FEATURE_RUNS_FILENAME` / `feature_dir` names reused as-is, not introduced). |
| Tidy-first (Standing Order #2) | Pass — the two lock accessors are exposed as a behaviour-preserving opening commit. |
| No heavy suites in mission | Pass — named gate files only. |
| `__all__` convention (kernel) | Pass — `event_log_lock_path` added to `kernel.event_log_append.__all__`, with a caller in `src/`. |

Post-design re-check: no new violations.

## Project Structure

### Documentation (this mission)

```
kitty-specs/local-event-log-retention-01M5ZCJP/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/doctor-event-logs.md
└── tasks.md            # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/kernel/event_log_append.py                  # __all__ += event_log_lock_path
src/runtime/next/run_lock.py                    # + try_run_cursor_lock (non-blocking)
src/specify_cli/state/contract.py               # RetentionRule, CleanupPolicy, StateSurface.cleanup_policy, surfaces_by_retention
src/specify_cli/core/ledger_retention.py        # RetentionLimits, load_retention_limits, RetentionConfigError
src/specify_cli/state/retention.py              # scan → RetentionPlan; apply
src/specify_cli/cli/commands/_event_logs_doctor.py  # register(app): doctor event-logs
docs/api/cli-commands.md                        # doctor event-logs block
docs/changelog/CHANGELOG.md                     # [Unreleased] Added
docs/ (how-to)                                  # cleaning up local event logs
tests/specify_cli/test_state_contract.py
tests/specify_cli/core/test_ledger_retention.py
tests/specify_cli/state/test_retention.py
tests/specify_cli/cli/commands/test_event_logs_doctor.py
```

**Structure Decision**: single project; files above.

## Complexity Tracking

None.

## Implementation Concern Map

### IC-01 — Per-surface cleanup policy

- **Purpose**: Make every registry surface declare how it is retained and cleaned, so cleanup has one owning policy (#5212).
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-013 (the selector half)
- **Affected surfaces**: `src/specify_cli/state/contract.py`, `tests/specify_cli/test_state_contract.py`
- **Sequencing/depends-on**: none
- **Risks**: 62 entries to classify by hand; the invariant tests (tracked ⇒ never/owner; prunable ⇒ ignored) catch the dangerous misclassifications. `to_dict()` gains a key; check readers of the serialized registry (state doctor JSON) for exact-key assertions.

### IC-02 — Retention limits and engine

- **Purpose**: Read `ledger.retention`, scan the policy-selected surfaces, and decide and carry out deletions safely.
- **Relevant requirements**: FR-005, FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, NFR-001, C-001, C-002
- **Affected surfaces**: `src/specify_cli/core/ledger_retention.py`, `src/specify_cli/state/retention.py`, `src/runtime/next/run_lock.py`, `src/kernel/event_log_append.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: lock order for a run (documented above); Mission completion on a coordination-topology Mission whose status log is not on this checkout reads as open (fail-safe); Windows deletion of a directory with an open handle (report per item, exit 1).

### IC-03 — `doctor event-logs` command, docs and changelog

- **Purpose**: Expose the engine as the dry-run-first doctor subcommand with human and JSON reports, and document it.
- **Relevant requirements**: FR-006, FR-012, C-003, C-004
- **Affected surfaces**: `src/specify_cli/cli/commands/_event_logs_doctor.py`, `docs/api/cli-commands.md`, `docs/changelog/CHANGELOG.md`, a how-to page
- **Sequencing/depends-on**: IC-02
- **Risks**: `test_docs_cli_reference_parity.py` requires the CLI reference block; exit-code contract is distinct from doctor's "1 = findings" convention (by operator-confirmed FR-012).
