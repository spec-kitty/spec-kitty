# Implementation Plan: Decision log integrity

**Branch**: `issue-4848-decision-open-lock` | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/decision-log-integrity-01M5ZAW0/spec.md`

## Summary

`open_decision` (`src/specify_cli/decisions/service.py`) saves the index entry under the
decisions lock (`decisions/index.json.lock`), releases it, and only then writes the artifact and
appends the `DecisionPointOpened` row. The idempotent retry calls
`_repair_missing_opened_event`, whose check and append also run without the lock. Two identical
opens, or two retries after an interrupted open, can therefore both append an opening row
(reproduced red on `origin/main` 581b5c46: 2 rows in both arms).

Approach, mirroring #6294 for the terminal verbs:

1. Hold the decisions lock for the whole open: dedup lookup, index append, artifact write and
   opening append on the fresh path; dedup lookup, check and repair append on the retry path.
2. Make the fold (`src/specify_cli/decisions/index_fold.py`) tolerate several opening rows for one
   decision when their payloads are equal apart from `recorded_at` (operator ruling 1).
3. Derive the reopen rule from `spec_kitty_events.decisionpoint.DECISION_POINT_TERMINAL_REOPEN`
   and delete the local `ALLOWED_TERMINAL_REOPEN` (operator ruling 2).

## Engineering Alignment

- Invariant: at most one `DecisionPointOpened` row per `decision_point_id` is appended by the CLI.
- Lock order stays decisions lock → Mission status lock (the emit takes the status lock inside);
  no code path takes them in reverse (#6294 established this, re-verified in research.md).
- No new writer, no rewrite: the writes gates' ledgers are unchanged.
- The retry's existence probe keeps reading through `_events_path` (read side). After the
  write-side pre-resolve in `open_decision` has materialized the coordination surface, the read
  side and the write side resolve to the same file, so no signature change is needed.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: spec-kitty-events 11.0.0 (`decisionpoint.DECISION_POINT_TERMINAL_REOPEN`), `kernel.locks.machine_file_lock`
**Storage**: `kitty-specs/<mission>/status.events.jsonl` (append-only JSONL), `decisions/index.json`
**Testing**: pytest; deterministic interleavings that pause the real emit (pattern of `tests/specify_cli/decisions/test_service_terminal_concurrency.py`), plus fold unit tests and a doctor-level test
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single
**Performance Goals**: the decisions lock is held across at most one opening append per call
**Constraints**: lock order decisions → status; no log rewrite; envelope half out of scope (C-002)
**Scale/Scope**: 2 source modules (`decisions/service.py`, `decisions/index_fold.py`), their tests, CHANGELOG

## Charter Check

- Single canonical authority: the reopen rule moves to its package owner; the fold remains the one decision fold. PASS.
- Architectural alignment (ADR 2026-10-22-1, ADR 2026-10-14-1): lock-scope and reader-only changes; nothing the Java write service would redo. PASS.
- ATDD / red-first: the interleaving tests land red before the fix. PASS (planned).
- Tidy-first (Standing Order #2): a behaviour-preserving extraction of the open critical section precedes the functional change. PASS (planned).
- Architectural gate discipline: no gate added; `test_event_log_writes_gate.py` and `test_status_events_writes_gate.py` stay green unchanged (no new write site, no new `feature_status_lock` composition). PASS.
- NO_FULL_HEAVY_SUITES_IN_MISSION: targeted tests, `make test-fast` and the two named gate files only. PASS.
- No dependency added or upgraded; DIRECTIVE_051 not triggered.

## Project Structure

### Documentation (this mission)

```
kitty-specs/decision-log-integrity-01M5ZAW0/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md          # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/decisions/
├── service.py        # open_decision lock scope; _repair_missing_opened_event under the lock
└── index_fold.py     # duplicate-opening tolerance; reopen rule from the package
tests/specify_cli/decisions/
├── test_service_open_concurrency.py   # new: deterministic open/retry interleavings
└── test_index_fold_duplicate_open.py  # new: fold tolerance + reopen-rule source
tests/decisions/
└── test_decisions_reconciler.py       # extended: doctor/--repair over a duplicated log
docs/changelog/CHANGELOG.md            # [Unreleased] entry
```

**Structure Decision**: single project; changes stay inside `src/specify_cli/decisions/`.

## Implementation Concern Map

### IC-01 — Open path serialized under the decisions lock

- **Purpose**: one opening row per decision under concurrent identical opens and concurrent retries.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-001
- **Affected surfaces**: `src/specify_cli/decisions/service.py` (`_locate_or_create_open_entry`, `open_decision`, `_repair_missing_opened_event` docstring), `src/specify_cli/cli/commands/decision.py` comments only if they describe the old scope
- **Sequencing/depends-on**: none
- **Risks**: lock order (verified decisions → status only); `open_decision` complexity must stay ≤ 15 — extract the locked section as a helper first (tidy-first).

### IC-02 — Fold tolerates identical duplicate openings

- **Purpose**: existing duplicated ledgers fold, doctor reports clean, `--repair` rebuilds.
- **Relevant requirements**: FR-003, C-003
- **Affected surfaces**: `src/specify_cli/decisions/index_fold.py` (`_fold_events`)
- **Sequencing/depends-on**: none
- **Risks**: must keep refusing differing payloads; must be order-independent (merge driver re-sorts by `(at, event_id)`).

### IC-03 — Reopen rule from the events package

- **Purpose**: one owner for the deferred → resolved rule.
- **Relevant requirements**: FR-004
- **Affected surfaces**: `src/specify_cli/decisions/index_fold.py`; callers `service._is_allowed_terminal_reopen`, `consolidation/drivers.py` keep calling `is_allowed_terminal_reopen` unchanged
- **Sequencing/depends-on**: none
- **Risks**: the package table is over `TerminalOutcome`, the CLI's over `DecisionStatus`; map through `_OUTCOME_TO_STATUS`.
