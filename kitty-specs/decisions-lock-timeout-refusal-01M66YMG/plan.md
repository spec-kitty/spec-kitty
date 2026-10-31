# Implementation Plan: Decisions Lock Timeout Refusal

**Branch**: `issue-6763-decisions-lock-timeout-refusal` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/decisions-lock-timeout-refusal-01M66YMG/spec.md`

## Summary

Three commands take the decisions sidecar lock (`decisions/index.json.lock`) through
`kernel.locks.machine_file_lock` at four sites, with the bounded 10 s wait
`_LOCK_ACQUIRE_TIMEOUT_S`. A timeout escapes as a raw `LockAcquireTimeout` traceback, and
`--json` callers get no document. The fix routes all four acquisitions through the one
existing translation, `decisions/service.py::_decisions_lock` (which raises
`DecisionError(LOCK_TIMEOUT)` = `DECISION_LOCK_TIMEOUT`), and renders that error at each
command's own error seam: the doctor's C2 envelope, `next`'s `error_code`/`next_step`
payload, and `repair-runtime-lock`'s `{status, code, message}` payload. Each site gets a
test that holds the lock and shortens the wait.

## Technical Context

**Language/Version**: Python 3.11+ (repo floor; `pyproject.toml`), Typer CLI
**Primary Dependencies**: none added. The seam (`kernel.locks`, `DecisionError`,
`DecisionErrorCode.LOCK_TIMEOUT`) already ships.
**Storage**: file-system sidecar lock `decisions/index.json.lock` (no schema change)
**Testing**: pytest; unit tier for the doctor and `next` dispatch, `integration` +
`git_repo` tier for `repair-runtime-lock` (it commits to a real repo). No full heavy suite
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: the `spec-kitty` CLI on Linux/macOS/Windows (the lock layer is
cross-platform; no platform-specific code is touched)
**Project Type**: single project (`src/`, `tests/`)
**Performance Goals**: no change to the happy path; a refusal appears within the existing
bounded wait (10 s default) and nothing waits longer
**Constraints**: exactly one translation seam; no new error code; each command keeps its
own error envelope (ADR `2026-10-27-2`); the diff stays on the lock-timeout surface
**Scale/Scope**: 4 acquisition sites, 3 commands, 4 new tests, 1 changelog entry, 1 docs
paragraph

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority (`DIRECTIVE_044`) | One translation seam (`_decisions_lock`); the doctor's duplicated `_LOCK_ACQUIRE_TIMEOUT_S` is deleted so there is one wait authority. |
| Architectural alignment (`DIRECTIVE_001`) | The service owns the lock and its refusal; commands only render. No command reaches into `kernel.locks` for this lock any more. |
| Locality of change (`DIRECTIVE_024`) / smallest viable diff | Four call-site swaps plus three small renderers; no surrounding refactor. |
| ATDD-first (`DIRECTIVE_034`) | Each site gets a failing test through the existing entry point before the fix. |
| Test quality (`DIRECTIVE_041`) | Tests assert the structured refusal, the exit code and the unchanged artifact tree — no shape-only pins. |
| No new dependency | None added; no supply-chain control applies. |

No violations, so `## Complexity Tracking` is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/decisions-lock-timeout-refusal-01M66YMG/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 decisions
├── quickstart.md        # How to reproduce the traceback before the fix
├── spec.md
├── checklists/requirements.md
├── issue-matrix.json    # (#6763)
├── traces/              # mission tracer files
└── tasks/               # work packages (filled by /spec-kitty.tasks)
```

No `data-model.md`: the mission persists nothing new — the lock file and the index it
guards already exist, and the refusal is an in-memory error object.
No `contracts/`: no interface is added or changed (same `DECISION_LOCK_TIMEOUT` code, same
per-command envelopes); `meta.json` records `"contracts": "none"` with its rationale.

### Source Code (repository root)

```
src/specify_cli/
├── decisions/service.py             # `_decisions_lock` — the only translation; annotation widened
├── cli/commands/_decisions_doctor.py# both doctor acquisition sites + C2 refusal renderer
├── cli/commands/next_cmd.py         # owned-`next` acquisition + its refusal renderer
└── cli/commands/decision.py         # runtime-lock repair acquisition + its code mapping

tests/
├── decisions/test_decisions_reconciler.py          # doctor: both acquisition sites
├── specify_cli/cli/commands/test_next_owned_lock_timeout.py  # owned `next`
└── integration/test_owned_decision_runtime_lock.py # `repair-runtime-lock`
```

**Structure Decision**: single project, existing modules only. Each command module keeps
its own renderer (that is where its error contract lives); the translation stays in
`decisions/service.py`.

## Implementation Concern Map

### IC-01 — One translation seam

- **Purpose**: every decisions-lock acquire in these three commands goes through
  `_decisions_lock`, so a timeout has one owner and one message.
- **Relevant requirements**: FR-001, NFR-003, C-001
- **Affected surfaces**: `src/specify_cli/decisions/service.py` (`_decisions_lock`
  signature annotation), `src/specify_cli/cli/commands/_decisions_doctor.py` (import the
  seam and the wait; delete the local `_LOCK_ACQUIRE_TIMEOUT_S`),
  `src/specify_cli/cli/commands/next_cmd.py`, `src/specify_cli/cli/commands/decision.py`
- **Sequencing/depends-on**: none
- **Risks**: the doctor's local `_decisions_lock_path`/`_LOCK_FILENAME` copy stays (two
  lockstep tests pin it); only the duplicated *timeout* constant goes away.

### IC-02 — Per-command refusal rendering

- **Purpose**: turn the seam's `DecisionError(LOCK_TIMEOUT)` into each command's own
  documented error shape, exit 1, with the retry remedy.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, NFR-002, C-002
- **Affected surfaces**: `_decisions_doctor.py::run_decisions_reconciliation` (C2 via
  `json_error`/`console.emit_json`, Rich line for human mode), `next_cmd.py`
  (`_emit_decisions_lock_timeout`, dual human/JSON like `_emit_meta_read_error`),
  `decision.py::_runtime_lock_error_code` (a `DecisionError` maps to its own code so the
  existing `{status, code, message}` renderer carries `DECISION_LOCK_TIMEOUT`)
- **Sequencing/depends-on**: IC-01
- **Risks**: the doctor must emit exactly one document (never a partial report then an
  error); `next` must refuse before printing a decision, so the catch wraps only the commit
  step.

### IC-03 — Red-first proof per site

- **Purpose**: pin each of the four acquisitions: hold the lock, shorten the wait, assert
  the structured refusal, exit 1, and an unchanged artifact tree; plus a control row on the
  same fixture proving a free lock still succeeds.
- **Relevant requirements**: SC-001, SC-002, SC-003, NFR-001
- **Affected surfaces**: `tests/decisions/test_decisions_reconciler.py`,
  `tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py` (new),
  `tests/integration/test_owned_decision_runtime_lock.py`
- **Sequencing/depends-on**: IC-01, IC-02 (the tests drive the real entry points)
- **Risks**: same-process `flock` contention is real only because each acquire opens its own
  descriptor — the tests hold the lock with `machine_file_lock`, never by pre-creating the
  file. `repair-runtime-lock` needs the owned-checkout fixture (real git), so that test is
  `integration`.
