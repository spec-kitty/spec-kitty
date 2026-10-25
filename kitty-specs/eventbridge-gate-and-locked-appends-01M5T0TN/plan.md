# Implementation Plan: EventBridge port, event-log writes gate and locked appends

**Branch**: `issue-6603-6606-eventbridge-gate-and-locked-appends` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/eventbridge-gate-and-locked-appends-01M5T0TN/spec.md`

## Summary

This Mission is step 0 of ADR 2026-10-22-1's migration order, and it closes the interim locking gap.

1. **EventBridge port.** Add the stdlib-only leaf `src/runtime/next/event_bridge.py`: `WorkPackageTransition`, `WorkPackageTransitionPort` and the binding. `EventBridgePort` is defined beside `RuntimeEventEmitter` in `_internal_runtime/events.py`, which grows it; a leaf avoids the `_internal_runtime` → engine → `status.emit` import cycle.
   - The local file adapter, `src/specify_cli/events/event_bridge.py`, writes through today's store primitives.
   - All three transition doors call the port: flat, batch and coordination.
2. **Interim locked append.** Add `src/kernel/event_log_append.py`. It takes an exclusive `kernel.locks` lock on a per-log (or per-family) lock file under `<git-common-dir>/spec-kitty-locks/event-logs/`, refuses a torn tail, then does one `O_APPEND` `os.write` followed by `fsync`. If git cannot be invoked, it refuses.
   - An optional precondition runs under the lock.
   - A lock-only context manager serves the glossary contract writer.
3. **Routing.** The eight G-5 writers, the `kitty-ops` Op-record appends and the glossary append go through it. Each keeps its own row bytes.
4. **Gate.** Add `tests/architectural/test_event_log_writes_gate.py`. It reuses the status gate's static scanner, extracted to `tests/architectural/_write_site_scan.py`, and freezes:
   - raw writes to every named event log outside the sanctioned modules;
   - every caller of the locked door and of `persistence.append_event`;
   - unresolved `.jsonl` writes.
   It has non-vacuity floors.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `kernel.locks` (`flock(2)` / `msvcrt`), `kernel.git_topology.git_common_dir`, `spec-kitty-events` 11.x (`persistence.append_event`, glossary only)
**Storage**: local JSONL files (append-only event logs)
**Testing**: pytest (unit, plus a multiprocess concurrency test and architectural AST gates); red-first per ADR 2026-07-17-1
**Target Platform**: Linux, macOS, Windows (the CLI)
**Project Type**: single (the CLI)
**Performance Goals**: one lock acquire per append unit; the gate runs in under 5 s on the whole tree
**Constraints**: byte-identical rows, no new validation authority, no transport, no new layer-ledger entry
**Scale/Scope**: about 12 writer sites in 10 modules, 2 doors and 1 new gate

## Charter Check

- **Single canonical authority:** one lock contract and one append primitive replace eight ad-hoc appends, and the port is the one transition door. Pass.
- **Architectural alignment:** the port is in `runtime` and the adapter in `specify_cli`, following ADR 2026-10-14-1 open question 1's default. The primitive is in `kernel`. The layer chain is respected. Pass.
- **ATDD / red-first:** every routed writer gets a torn-tail refusal test that is red before routing. The gate's synthetic floors are red against a scanner that matches nothing. Pass.
- **Quality standing orders:** complexity is 15 or below, repeated literals become constants, there are no new suppressions, and the tracer files are seeded. Pass.
- **Terminology:** "Mission" throughout. Bare "routing" is avoided: an append "goes through" the locked door. Pass.

## Project Structure

### Documentation (this mission)

```
kitty-specs/eventbridge-gate-and-locked-appends-01M5T0TN/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/kernel/event_log_append.py                    # new: interim locked append primitive
src/kernel/locks.py                               # LOCK_DIRECTORY moves here (re-exported by core.checkout_file_lock)
src/runtime/next/event_bridge.py                  # new: stdlib-only port leaf + binding
src/runtime/next/_internal_runtime/events.py      # EventBridgePort grows RuntimeEventEmitter
src/specify_cli/events/event_bridge.py            # new: local file adapter + door accessor
src/specify_cli/status/emit.py                    # door 1
src/specify_cli/coordination/transaction.py       # door 2
src/specify_cli/{invocation,events,mission_v1,policy,missions}/...  # routed writers
src/runtime/next/_internal_runtime/engine.py      # routed run journal
src/charter/activation/_io.py                     # routed provenance
src/glossary/events.py                            # contract append under the lock
tests/kernel/test_event_log_append.py             # new
tests/architectural/test_event_log_writes_gate.py # new
```

**Structure Decision**: single project. The new modules sit beside their siblings.

## Implementation Concern Map

### IC-01 — Interim locked append primitive

- **Purpose**: one lock contract and one single-write append, so no event log interleaves or extends a torn tail.
- **Relevant requirements**: FR-007, FR-011, NFR-002, NFR-003, C-002, C-003
- **Affected surfaces**: `src/kernel/event_log_append.py`, `src/kernel/locks.py`, `src/specify_cli/core/checkout_file_lock.py`
- **Sequencing/depends-on**: none
- **Risks**:
  - The lock path must be identical across worktrees: resolve the git common dir, and hash the resolved, case-normalised log path.
  - Without git, the lock falls back to `<log>.event-log.lock`; if git cannot be invoked, the append refuses.
  - A missing parent raises before any lock is touched (the #6367 marker class).
  - Per-record logs (`kitty-ops/<op>.jsonl`) share one family lock.

### IC-02 — Route the unlocked writers

- **Purpose**: every G-5 writer, the Op-record appends and the glossary append take the lock.
- **Relevant requirements**: FR-008, FR-009, FR-010, NFR-001
- **Affected surfaces**: `invocation/lifecycle.py`, `invocation/propagator.py`, `invocation/writer.py`, `runtime/next/next_invocation_lifecycle.py` (pairing warns on refusal), `events/decision_log.py`, `mission_v1/events.py`, `runtime/next/_internal_runtime/engine.py`, `policy/audit.py`, `missions/_archive.py`, `charter/activation/_io.py`, `glossary/events.py`
- **Sequencing/depends-on**: IC-01
- **Risks**:
  - Keep each writer's bytes and its parent-directory behaviour.
  - Keep `O_NOFOLLOW` and the identity check for Op records.
  - Callers that swallow failures keep swallowing them; the new errors subclass `OSError`.

### IC-03 — EventBridge port and the two doors

- **Purpose**: the work package transition reaches the log through one port (ADR D-2, open question 6 default).
- **Relevant requirements**: FR-001 to FR-004, C-001, C-004, C-005
- **Affected surfaces**: `runtime/next/event_bridge.py`, `runtime/next/_internal_runtime/events.py`, `specify_cli/events/event_bridge.py`, `status/emit.py`, `coordination/transaction.py`, `status/_unsafe.py` (`ALLOWED_CALLERS`: a swap; `coordination.transaction` no longer imports a door and leaves, and the adapter enters)
- **Sequencing/depends-on**: none
- **Risks**:
  - Import cycles between status and runtime: the adapter imports lazily.
  - The shrink-only allowlist does not grow: the transaction entry is swapped for the adapter. ADR D-1 says the primitives become private to the bridge.
  - The binding is the second half of the one port, not a second emitter registry; a tripwire pins that open-core binds none outside tests.

### IC-04 — Multi-log writes gate and docs

- **Purpose**: a new event-log writer fails CI; the docs record the lock contract and the port.
- **Relevant requirements**: FR-005, FR-006, NFR-004
- **Affected surfaces**: `tests/architectural/test_event_log_writes_gate.py`, `tests/architectural/_write_site_scan.py` (extracted), `tests/architectural/test_status_events_writes_gate.py`, `docs/architecture/event-ledger-writers-and-readers.md`, `docs/development/reference/events-in-core.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-02, IC-03 (it freezes the post-routing writers)
- **Risks**:
  - The static resolver misses dynamic paths. Unresolved `.jsonl` writes are pinned, not passed.
