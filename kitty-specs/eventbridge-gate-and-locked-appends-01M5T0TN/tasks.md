# Tasks: EventBridge port, event-log writes gate and locked appends

**Mission**: `eventbridge-gate-and-locked-appends-01M5T0TN` | **Branch**: `issue-6603-6606-eventbridge-gate-and-locked-appends` → PR to `main`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Move `LOCK_DIRECTORY` into `kernel.locks`; re-export from `core.checkout_file_lock` | WP01 | |
| T002 | `kernel/ledger_append.py`: lock-path rule, `ledger_lock`, `append_ledger_lines`, errors | WP01 | |
| T003 | Unit tests: framing, torn tail, precondition, no-follow, missing parent, lock-path rule | WP01 | |
| T004 | Concurrency test (8 processes × 50 rows) and lock-timeout test | WP01 | |
| T005 | Red-first torn-tail tests for the eight G-5 writers | WP02 | |
| T006 | Route lifecycle, propagator, decision log, Mission v1 events | WP02 | [P] |
| T007 | Route run journal, policy audit, archive registry, encoding provenance | WP02 | [P] |
| T008 | Glossary contract append under `ledger_lock` | WP02 | |
| T009 | Red-first torn-tail / lock tests for the Op-record appends | WP03 | |
| T010 | Route `_append_line_no_follow` (index, closure spine) | WP03 | |
| T011 | Route `write_completed`, `append_correlation_link`, `write_glossary_observation` with the identity check as precondition | WP03 | |
| T012 | EventBridge port module (`runtime/next/event_bridge.py`) with binding registry | WP04 | |
| T013 | Local file adapter (`specify_cli/events/event_bridge.py`) | WP04 | |
| T014 | Flat-shell door (`_persist_prepared`) goes through the port | WP04 | |
| T015 | Coordination door (`BookkeepingTransaction.append_events`) goes through the port | WP04 | |
| T016 | Port tests: recording adapter in both doors, byte stability, conflict binding; `ALLOWED_CALLERS` entry | WP04 | |
| T017 | Multi-log writes gate with ledgers and non-vacuity floors | WP05 | |
| T018 | Architectural pin: both doors call the port | WP05 | |
| T019 | Docs: writers/readers map, events-in-core lock contract, changelog | WP05 | |

## WP01 — Interim locked append primitive (foundation)

**Goal**: one locked, torn-tail-refusing, single-write, fsynced append in `kernel`. **Priority**: P1. **Independent test**: `tests/kernel/test_ledger_append.py`.
**Prompt**: [tasks/WP01-interim-locked-append-primitive.md](tasks/WP01-interim-locked-append-primitive.md)

T001 Move LOCK_DIRECTORY into kernel.locks (WP01)
T002 kernel/ledger_append.py primitive (WP01)
T003 Unit tests (WP01)
T004 Concurrency and lock-timeout tests (WP01)

Dependencies: none.

## WP02 — Route the eight G-5 writers and the glossary append

**Goal**: every G-5 site takes the lock and keeps its bytes. **Priority**: P1.
**Prompt**: [tasks/WP02-route-unlocked-event-log-writers.md](tasks/WP02-route-unlocked-event-log-writers.md)

T005 Red-first torn-tail tests (WP02)
T006 Route invocation/events/mission_v1 writers (WP02)
T007 Route runtime/policy/missions/charter writers (WP02)
T008 Glossary append under the lock (WP02)

Dependencies: WP01.

## WP03 — Op-record appends take the lock

**Goal**: `invocation/writer.py` appends are locked; identity check under the lock. **Priority**: P1.
**Prompt**: [tasks/WP03-op-record-appends-take-the-lock.md](tasks/WP03-op-record-appends-take-the-lock.md)

T009 Red-first tests (WP03)
T010 Route the no-follow line appender (WP03)
T011 Route the validated appends (WP03)

Dependencies: WP01.

## WP04 — EventBridge port behind the two transition doors

**Goal**: both WP transition doors go through the port; default adapter writes today's bytes. **Priority**: P1.
**Prompt**: [tasks/WP04-eventbridge-port-and-doors.md](tasks/WP04-eventbridge-port-and-doors.md)

T012 Port module (WP04)
T013 Local file adapter (WP04)
T014 Flat-shell door (WP04)
T015 Coordination door (WP04)
T016 Port tests (WP04)

Dependencies: none.

## WP05 — Multi-log writes gate and docs

**Goal**: new event-log writers fail CI; docs record the port and lock contract. **Priority**: P1.
**Prompt**: [tasks/WP05-multi-log-writes-gate-and-docs.md](tasks/WP05-multi-log-writes-gate-and-docs.md)

T017 Multi-log writes gate (WP05)
T018 Door pin (WP05)
T019 Docs and changelog (WP05)

Dependencies: WP02, WP03, WP04.

## Parallelization

WP01 and WP04 can run in parallel; WP02 and WP03 can run in parallel after WP01; WP05 last.
MVP: WP01 + WP02 (closes the #6606 corruption risk).
