# Tasks: Activation writes under the charter synthesis lock

**Mission**: `activation-writes-under-synthesis-lock-01M68ZS1` · **Branch**: `issue-6719-activation-writes-under-synthesis-lock` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Failing two-writer test: a `charter deactivate` racing a synthesis activation append | WP01 | |
| T002 | Failing two-writer test: the migration's manifest stamp vs a concurrent synthesis manifest write | WP01 | [P] |
| T003 | Refusal tests: activate/deactivate/preset/migration against a held synthesis lock (`CHARTER_SYNTHESIS_LOCK_HELD`, nothing written) | WP01 | [P] |
| T004 | Shared lock-window helper `synthesis_locked` on the write seams; `ActiveCharterManager.activate`/`.deactivate` hold it across read → plan → commit → restamp | WP02 | |
| T005 | `preset_application` plan+apply under the same window | WP02 | |
| T006 | `activation_engine.promote_activations` self-guards its own read-modify-write | WP02 | |
| T007 | `activation_ledger.apply_ledger_migration` holds the window across ledger write → stamp → strips | WP02 | [P] |
| T008 | `ERROR_CODES.md` documents the two lock codes for the activation surface | WP02 | [P] |
| T009 | `charter activate`/`deactivate`: hold the command's activation window, convert the lock errors to `CodedRefusal` (text + `--json`) | WP03 | |
| T010 | `--preset` and the `--json` builder render the same refusal | WP03 | |
| T011 | `docs/changelog/CHANGELOG.md` `[Unreleased]` entry naming #6719 | WP03 | [P] |
| T012 | Docs: the lock/refusal behaviour on the charter activation how-to | WP03 | [P] |

## Phase 1 — Tests first (red)

### WP01 — Two-writer and refusal tests for the activation writes

**Goal**: the four races/refusals of #6719 are pinned by tests that fail on `main` and pass with the fix. **Priority**: P1. **Prompt**: [tasks/WP01-lock-race-tests.md](tasks/WP01-lock-race-tests.md)
**Independent test**: `uv run pytest tests/charter/activation/test_activation_writes_under_synthesis_lock.py` — red before WP02/WP03, green after.

T001 Failing two-writer test: a `charter deactivate` racing a synthesis activation append (WP01)
T002 Failing two-writer test: the migration's manifest stamp vs a concurrent synthesis manifest write (WP01)
T003 Refusal tests: activate/deactivate/preset/migration against a held synthesis lock (`CHARTER_SYNTHESIS_LOCK_HELD`, nothing written) (WP01)

Dependencies: none. Risk: a handshake that waits on a sleep instead of on a provable lock contention is flaky — use the #6453 `_Handshake` pattern (`_LockCore.try_lock_once` returning `False`).

## Phase 2 — The write seams

### WP02 — Take the existing synthesis lock at the activation write seams

**Goal**: every activation-config / manifest read-modify-write in the four seams runs under the run-wide synthesis lock, re-entrantly. **Priority**: P1. **Prompt**: [tasks/WP02-write-seams-take-the-lock.md](tasks/WP02-write-seams-take-the-lock.md)
**Independent test**: T001/T002/T003 of WP01 go green; the existing charter activation, preset, synthesis-lock and activation-ledger suites stay green.

T004 Shared lock-window helper `synthesis_locked` on the write seams; `ActiveCharterManager.activate`/`.deactivate` hold it across read → plan → commit → restamp (WP02)
T005 `preset_application` plan+apply under the same window (WP02)
T006 `activation_engine.promote_activations` self-guards its own read-modify-write (WP02)
T007 `activation_ledger.apply_ledger_migration` holds the window across ledger write → stamp → strips (WP02)
T008 `ERROR_CODES.md` documents the two lock codes for the activation surface (WP02)

Dependencies: WP01 (red tests define the contract). Risk: double acquisition must stay re-entrant; a `with`-nesting deadlock shows up immediately in `charter deactivate --resynthesize`.

## Phase 3 — Command surface and docs

### WP03 — The CLI window, the coded refusal and the changelog

**Goal**: `charter activate`/`deactivate` (positional, `--preset`, `--json`) hold their activation window and render a held lock as `CHARTER_SYNTHESIS_LOCK_HELD`; the user-facing change is documented. **Priority**: P1. **Prompt**: [tasks/WP03-cli-window-and-changelog.md](tasks/WP03-cli-window-and-changelog.md)
**Independent test**: T003 goes green for the CLI paths; `Error (CHARTER_SYNTHESIS_LOCK_HELD)` in text and the same code in the `--json` envelope.

T009 `charter activate`/`deactivate`: hold the command's activation window, convert the lock errors to `CodedRefusal` (text + `--json`) (WP03)
T010 `--preset` and the `--json` builder render the same refusal (WP03)
T011 `docs/changelog/CHANGELOG.md` `[Unreleased]` entry naming #6719 (WP03)
T012 Docs: the lock/refusal behaviour on the charter activation how-to (WP03)

Dependencies: WP01 (T003's CLI assertions), WP02 (the seam behaviour they exercise). Risk: the refusal must not mask a real `precondition_changed` regression — keep both codes distinct.
