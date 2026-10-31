# Implementation Plan: Decisions lock keyed on the event log

**Branch**: `issue-6765-decisions-lock-log-anchor` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/decisions-lock-log-anchor-01M67JK0/spec.md`

## Summary

`open_decision` and the terminal verbs (`resolve`/`defer`/`cancel`) hold one decisions
lock across the dedup lookup, the index append, the artifact write and the event append.
That lock is `decisions/index.json.lock` — keyed on the per-checkout **ledger directory**
— while the row it protects is appended to the Mission **event log**, resolved
independently and, on a coordination topology, on a different partition. Two checkouts
that write one log therefore hold two lock files and do not serialize.

The fix keys an additional lock on the event log itself, reusing the one existing
anchor→lock contract (`kernel.event_log_append.event_log_lock_path`: digest of the
resolved anchor under `<git-common-dir>/spec-kitty-locks/event-logs/`). Both forward
write paths take the anchor lock and then the existing ledger-dir sidecar, through the
existing `_decisions_lock` helper, so the timeout/refusal surface is untouched (that is
PR #6841's) and the sidecar's own contract (reconciler, `repair-runtime-lock`, gitignore
provisioning, `next`'s owned commit guard) is preserved verbatim.

## Technical Context

**Language/Version**: Python 3.11 (`requires-python >=3.11`), stdlib `fcntl`/`msvcrt` via `kernel.locks`
**Primary Dependencies**: none added — `kernel.event_log_append`, `kernel.locks`, existing `specify_cli` seams
**Storage**: filesystem locks and JSON/JSONL mission artifacts (`decisions/index.json`, `status.events.jsonl`)
**Testing**: pytest; unit + integration with real git fixtures (`tests/integration/conftest.py`, `make_owned_checkouts`)
**Target Platform**: POSIX and Windows (the lock primitive is cross-OS; the anchor path is pure `pathlib` + git common dir)
**Project Type**: single Python CLI package (`src/specify_cli`, `src/kernel`, `src/mission_runtime`)
**Performance Goals**: NFR-002 — one extra `flock` acquisition per decision write; no extra scan, worktree or subprocess beyond the git-common-dir probe the lock path already performs
**Constraints**: C-001 no timeout-reporting change; C-002 keep the sidecar and its machinery; C-003 reuse `event_log_lock_path`; C-004 one global lock order
**Scale/Scope**: one production module (`src/specify_cli/decisions/service.py`), one new test module, one changelog entry, targeted docs

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Verdict |
|---|---|
| Single canonical authority | PASS — no second lock-placement scheme: the anchor path comes from `kernel.event_log_append.event_log_lock_path`, the digest owner |
| Architectural alignment | PASS — `specify_cli.decisions` consumes `kernel` primitives (existing direction); no new cross-package edge |
| ATDD-first (DIRECTIVE_034) | PASS — failing test through `open_decision` committed before the production edit |
| Glossary/terminology | PASS — "event log" for `status.events.jsonl`, "decision ledger" for `decisions/`; no new term |
| Lock primitive ban (DIRECTIVE_043) | PASS — acquires through `kernel.locks.machine_file_lock` via `_decisions_lock`; no raw `flock`/`filelock` |
| Test suite quality (DIRECTIVE_041) | PASS — one new module guarding a standing invariant; no dev-assist scaffolding expected |
| Pack tiers | PASS — no doctrine or pack content changes |
| User customization | PASS — no template/agent-copy changes |
| Doctrinal sources | PASS — the #4848/#4966/#5925/#6628 decisions are read from the code, `research.md` and the changelog, not from memory |

No violations; the Complexity Tracking table stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/decisions-lock-log-anchor-01M67JK0/
├── plan.md              # This file
├── research.md          # Discovery (D-1..D-6) + plan-phase decisions (P-1..P-3)
├── data-model.md        # Lock identities, invariants, the two-lock acquisition order
├── reasons-canvas.md    # SPDD canvas (charter paradigm)
├── quickstart.md        # How to verify the serialization by hand
└── spec.md
```

No `contracts/` — this mission defines no external interface. `meta.json` records
`"contracts": "none"` with the rationale.

### Source Code (repository root)

```
src/
├── kernel/
│   ├── event_log_append.py        # reuse: event_log_lock_path (the anchor→lock contract)
│   └── locks.py                   # reuse: machine_file_lock
└── specify_cli/decisions/
    ├── service.py                 # CHANGE: anchor lock path + two-lock context manager;
    │                              #         open_decision and _terminal_command use it
    ├── emit.py                    # unchanged (still takes the Mission status lock inside)
    └── store.py                   # unchanged

tests/
└── specify_cli/decisions/
    ├── test_service_terminal_concurrency.py   # unchanged (ratchet)
    └── test_decisions_lock_log_anchor.py      # NEW: cross-checkout serialization + keying
```

**Structure Decision**: single project. The change is confined to the decisions service
module; the kernel lock contract is consumed, not modified.

## Implementation Concern Map

### IC-01 — The two-lock acquisition on the write path

- **Purpose**: make every decision *write* hold a lock keyed on the event log it writes to, in addition to the ledger-dir sidecar it already holds, so writers of one log serialize across checkouts.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-003, C-003, C-004
- **Affected surfaces**: `src/specify_cli/decisions/service.py` (`_decisions_lock_path`, new anchor helper, new two-lock context manager, `open_decision`, `_terminal_command`)
- **Sequencing/depends-on**: none
- **Risks**: taking the anchor before the sidecar is the only order that cannot invert an existing take; a bounded wait must not appear on the open path (NFR-001); `dry_run` must still take nothing.

### IC-02 — Proving the serialization and the keying

- **Purpose**: prove the defect (overlapping critical sections pre-fix) and the invariant (one lock per log, none per ledger dir), without over-serializing distinct logs.
- **Relevant requirements**: FR-003, FR-004, SC-001, SC-002, SC-003, SC-004, NFR-004
- **Affected surfaces**: `tests/specify_cli/decisions/test_decisions_lock_log_anchor.py` (new), pre-existing decision suites as the ratchet
- **Sequencing/depends-on**: IC-01 (the test is written first and fails until IC-01 lands)
- **Risks**: a test that only compares lock paths for identical ledger dirs is vacuous (see research D-3); the reproduction must drive `open_decision` and observe overlap, with a same-fixture positive control that the probe can see a shared lock when one exists.

### IC-03 — Recording the change for reviewers and users

- **Purpose**: state the new lock identity, the order, and what deliberately did not change (the sidecar contract, the timeout surface).
- **Relevant requirements**: NFR-003, C-001, C-002
- **Affected surfaces**: `docs/changelog/CHANGELOG.md` `[Unreleased]`; the docstrings of the touched functions are the in-code documentation surface
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the sibling PR #6841 edits the same neighbourhood's refusal wording — the changelog entry must describe keying only, never timeout behaviour.

## Post-Design Charter Re-check

All gates above still hold after Phase 1: the design adds one lock identity sourced from
an existing kernel authority, changes no interface, and adds no dependency. No
`contracts/` directory is created because the mission defines no external interface
(`meta.json` records `"contracts": "none"`).
