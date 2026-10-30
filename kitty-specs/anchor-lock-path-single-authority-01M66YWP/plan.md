# Implementation Plan: One kernel helper for anchor-keyed lock paths

**Branch**: `issue-6727-anchor-lock-paths` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/anchor-lock-path-single-authority-01M66YWP/spec.md`
**Input**: Mission specification from `kitty-specs/anchor-lock-path-single-authority-01M66YWP/spec.md`, grounded in `research.md` (issue #6727, follow-up to #6453).

## Summary

Three lock families repeat one rule: resolve the anchor, `os.path.normcase` it, digest it, and
place the result under `<git-common-dir>/spec-kitty-locks/…`, falling back to a family-specific
path outside git. Add `kernel.locks.anchored_lock_path` — the single implementation of that rule
— and route `event_log_lock_path`, `synthesis_lock_path` and the Mission checkout-claim lock
through it, keeping every family's lock name, non-git fallback and git-unavailable policy
byte-identical. A value-pinned contract test and a source-shape gate make the shared rule, and
the absence of a fourth copy, fail CI instead of review.

## Technical Context

**Language/Version**: Python 3.11 (repository floor; `from __future__ import annotations` style)
**Primary Dependencies**: stdlib only in the touched code (`hashlib`, `os`, `pathlib`) plus the
existing intra-kernel modules `kernel.git_topology` (git common-dir probe) and
`kernel.locks.LOCK_DIRECTORY`; no third-party dependency is added to the kernel (C-001,
NFR-004). Tests use `pytest` (existing dev dependency).
**Storage**: local filesystem only — lock files under `<git-common-dir>/spec-kitty-locks/`, held
through `kernel.locks.machine_file_lock`. No database, no network.
**Testing**: `pytest` unit tests, `pytest.mark.unit`/`git_repo`; red-first contract tests in
`tests/kernel/test_lock_paths.py`, the existing family suites unchanged, and one
`tests/architectural/` source-shape gate. Targeted suites only
(`NO_FULL_HEAVY_SUITES_IN_MISSION`).
**Target Platform**: POSIX and Windows (the digest is over `os.path.normcase(resolved)`, so the
Windows form lower-cases and backslash-normalises; the POSIX-only golden test keeps its skip
marker).
**Project Type**: single Python package (`src/`) + `tests/`.
**Performance Goals**: a lock-path computation costs at most one `git rev-parse` (already
`lru_cache`d in `kernel.git_topology`) and zero when the caller supplies the common dir; no
added subprocess, filesystem write or import-time work.
**Constraints**: lock file names are frozen (C-001); the helper stays a single linear function
with cyclomatic complexity ≤ 15 (NFR-003); `kernel.locks` keeps only stdlib and intra-kernel
imports (NFR-004); no user-visible behaviour change, so no changelog entry (C-005).
**Scale/Scope**: 4 `src/` modules touched (`kernel/locks.py`, `kernel/event_log_append.py`,
`charter/activation/synthesizer/synthesis_lock.py`, `specify_cli/status/locking.py`), 1 new test
module, 1 new architectural gate, 2 doc pages, ~7 existing test modules kept green.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
| --- | --- |
| Single canonical authority (DIRECTIVE_044 / `canonical-source-unification`) | The rule gets exactly one implementation (`kernel.locks.anchored_lock_path`); the three copies are deleted, not aliased. The gate (FR-006) keeps them deleted. |
| Architectural alignment / kernel tier (C-001, DIRECTIVE_001) | The helper sits in `kernel`, the lowest tier, beside `LOCK_DIRECTORY`; `charter` and `specify_cli` may import it, the reverse never. |
| ATDD-first (C-011, DIRECTIVE_034) | The contract tests and the source-shape gate are committed red before the helper exists; the three families' existing path tests are the behaviour-preserving half of the proof. |
| Locality of change / smallest viable diff (DIRECTIVE_024, `change-apply-smallest-viable-diff`) | Only the three named families move. `feature_status_lock_path`, `project_event_log_lock`, `review/verdict_commit_queue` and `design/receipts` keep their construction (C-002), with a docstring line saying why. |
| Test quality, no vacuous gates (DIRECTIVE_041) | Each new test asserts a literal path or a real failure mode (bad algorithm, no-probe fast path, reintroduced copy). Nothing is asserted indirectly through the helper it tests. |
| Terminology canon | "Mission", "anchor", "lock family", "common dir"; no new synonyms, no "feature" in new prose (C-006). |
| Documentation standards | The two pages that state the contract (`docs/architecture/event-ledger-writers-and-readers.md`, `docs/development/reference/lock-interop-spike.md`) name the helper as the one implementation; the contract text itself does not change (FR-008). |
| Changelog discipline | No `[Unreleased]` entry: no user- or operator-visible behaviour, lock name, error code or message changes (C-005). The closest precedent, #3773 (extract the shared FileLock primitive), also shipped without one. |

No charter violations to justify; Complexity Tracking stays empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/anchor-lock-path-single-authority-01M66YWP/
├── spec.md              # Mission spec (committed)
├── research.md          # Grounding, behaviour inventory, decisions D1-D5 (committed)
├── plan.md              # This file
├── data-model.md        # Phase 1: the value shapes and invariants of the rule
└── tasks.md             # Phase 2 (/spec-kitty.tasks)
```

`contracts/`: **none** — this Mission defines no interface (it is an internal consolidation),
so `meta.json` records `"contracts": "none"` with a rationale for the `accept` waiver.
`quickstart.md`: **none** — there is no user-facing surface to quick-start.

### Source Code (repository root)

```
src/
├── kernel/
│   ├── locks.py                                  # + anchored_lock_path (+ __all__ entry)
│   ├── event_log_append.py                       # event_log_lock_path -> helper
│   └── git_topology.py                           # unchanged (imported by the helper)
├── charter/activation/synthesizer/
│   └── synthesis_lock.py                         # synthesis_lock_path -> helper
└── specify_cli/status/
    └── locking.py                                # _checkout_claim_lock_path -> helper

tests/
├── kernel/test_lock_paths.py                     # NEW: contract pinned by value
├── architectural/test_anchor_lock_path_single_owner.py   # NEW: no-fourth-copy gate
├── kernel/test_event_log_append.py               # unchanged (behaviour preservation)
├── charter/synthesizer/test_synthesis_lock.py    # unchanged
├── status/test_checkout_claim_lock.py            # unchanged
└── status/test_journal_lock_unification.py       # unchanged
```

**Structure Decision**: the existing single-package layout. The helper goes into the existing
`kernel/locks.py` rather than a new module because `LOCK_DIRECTORY` — the other half of the rule
— already lives there, and the issue names `kernel.locks.anchored_lock_path`.

## Complexity Tracking

No charter violations. Nothing to justify.

## Implementation Concern Map

### IC-01 — The helper and its pinned contract

- **Purpose**: Create the one implementation of the anchored lock-path rule, with its contract
  fixed by value before any caller moves.
- **Relevant requirements**: FR-001, FR-005, NFR-003, NFR-004, C-004
- **Affected surfaces**: `src/kernel/locks.py` (`anchored_lock_path`, `__all__`),
  `tests/kernel/test_lock_paths.py`
- **Sequencing/depends-on**: none
- **Risks**: the parameter set must cover exactly the three shapes and no more (a knob no caller
  uses is a defect); the `probe_dir` parameter is load-bearing because the event-log anchor may
  not exist yet (`kernel.git_topology._probe_dir` only normalises an existing file); the
  sha1 path must pass `usedforsecurity=False` so the security lint stays quiet; `normcase` must
  stay applied to the *resolved* string, exactly as the three copies do it.

### IC-02 — Route the three families, and gate the fourth copy

- **Purpose**: Move all three families onto the helper without changing a single lock name,
  fallback or refusal, then make a reintroduced copy fail CI.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-006, FR-007, FR-008, NFR-001, NFR-002,
  C-001, C-002, C-003
- **Affected surfaces**: `src/kernel/event_log_append.py`,
  `src/charter/activation/synthesizer/synthesis_lock.py`, `src/specify_cli/status/locking.py`,
  `tests/architectural/test_anchor_lock_path_single_owner.py`,
  `docs/architecture/event-ledger-writers-and-readers.md`,
  `docs/development/reference/lock-interop-spike.md`
- **Sequencing/depends-on**: IC-01
- **Risks**: the status family must pass its *degraded* common dir so it keeps never raising
  (its `_git_common_dir` has three fallback branches); `_is_checkout_claim_lock_key` pattern-matches
  the lock *name*, so the sha1/16 shape must be exact; the gate must not fire on the fixed-name
  lock files in `review/` and `design/` (they name files under `LOCK_DIRECTORY` but digest
  nothing), and its non-vacuity proof (re-adding a copy fails it) is part of the test.
