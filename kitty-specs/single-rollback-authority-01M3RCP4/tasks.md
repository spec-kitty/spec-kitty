# Tasks: Every post-mutation consolidate exit rolls back through one authority

**Mission**: `single-rollback-authority-01M3RCP4` · **Issue**: #5385 · **Branch**: `claude/5385-single-rollback-authority-qqt180` (planning base and merge target)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first real-git repro: one planted failure per post-mutation phase | WP01 | |
| T002 | One `try` around the post-mutation span in the driver; hardened `_report_rollback` | WP01 | |
| T003 | Retire the revert-based rollback helpers and their dead state | WP01 | |
| T004 | Re-pin the tests that pinned the old keep-done / revert contract | WP01 | |
| T005 | Grow the AST pin (span wrapped; no revert-based helper) with self-mutation cases | WP01 | |
| T006 | Targeted runs, ruff, format, mypy, planted-break proof | WP01 | |
| T007 | Red-first real-CLI repro: LANES mission on protected `main` refused before mutation | WP02 | |
| T008 | Extract the transaction's pre-flight policy gate; add lock-free `preflight_refusal` | WP02 | |
| T009 | `status_write_refusal` probe in the transactional status door | WP02 | |
| T010 | Consolidation preflight + pre-lock call in the executor | WP02 | |
| T011 | `--dry-run` parity in the forecast | WP02 | [P] |
| T012 | Readable `BookkeepingPolicyRefused` at the consolidate command layer | WP02 | [P] |
| T013 | Re-home the `--abort` repro fixture that relied on the #5385 crash | WP01 | |
| T014 | ADR 2026-09-19-1 follow-up note: residual #5385 closed | WP03 | [P] |
| T015 | CLAUDE.md consolidation section update | WP03 | [P] |
| T016 | CHANGELOG `[Unreleased]` entry | WP03 | [P] |

## WP01 — One rollback door for the post-mutation span

**Goal**: every non-zero exit, exception or interrupt between `_phase_merge_lanes` and `_phase_reconcile_before_teardown` rolls back through `rollback_to_snapshot`; the revert-based helpers are gone; the pin proves it. **Priority**: P1. **Prompt**: [tasks/WP01-one-rollback-door.md](tasks/WP01-one-rollback-door.md) (~330 lines).

T001 Red-first real-git repro: one planted failure per post-mutation phase (WP01)
T002 One `try` around the post-mutation span in the driver; hardened `_report_rollback` (WP01)
T003 Retire the revert-based rollback helpers and their dead state (WP01)
T004 Re-pin the tests that pinned the old keep-done / revert contract (WP01)
T005 Grow the AST pin (span wrapped; no revert-based helper) with self-mutation cases (WP01)
T006 Targeted runs, ruff, format, mypy, planted-break proof (WP01)
T013 Re-home the `--abort` repro fixture that relied on the #5385 crash (WP01)

**Independent test**: the T001 repro is red on `c34481d7` and green after T002/T003. **Dependencies**: none. **Risks**: re-pins must assert the new contract, never drop coverage; `typer.Exit(0)` must pass through.

## WP02 — Protected-target preflight

**Goal**: a consolidation whose done bookkeeping the workflow mutation policy would refuse is refused before the first mutation (and in `--dry-run`), with the policy's own code and remedy. **Priority**: P1. **Prompt**: [tasks/WP02-protected-target-preflight.md](tasks/WP02-protected-target-preflight.md) (~320 lines).

T007 Red-first real-CLI repro: LANES mission on protected `main` refused before mutation (WP02)
T008 Extract the transaction's pre-flight policy gate; add lock-free `preflight_refusal` (WP02)
T009 `status_write_refusal` probe in the transactional status door (WP02)
T010 Consolidation preflight + pre-lock call in the executor (WP02)
T011 `--dry-run` parity in the forecast (WP02)
T012 Readable `BookkeepingPolicyRefused` at the consolidate command layer (WP02)

**Independent test**: T007 repro. **Dependencies**: depends on WP01 (both edit `consolidation/executor.py`; the preflight call is one out-of-map line). **Risks**: over-refusal; the probe must follow the real write's arm selection.

## WP03 — Docs and changelog

**Goal**: shipped behaviour documented. **Priority**: P2. **Prompt**: [tasks/WP03-docs-and-changelog.md](tasks/WP03-docs-and-changelog.md) (~120 lines).

T014 ADR 2026-09-19-1 follow-up note: residual #5385 closed (WP03)
T015 CLAUDE.md consolidation section update (WP03)
T016 CHANGELOG `[Unreleased]` entry (WP03)

**Dependencies**: depends on WP01, WP02.

## MVP

WP01 alone closes the P1 defect class (the #5385 crash is rolled back in-process); WP02 removes the trigger up front.
