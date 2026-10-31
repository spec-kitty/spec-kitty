# Implementation Plan: Activation writes under the charter synthesis lock

**Branch**: `issue-6719-activation-writes-under-synthesis-lock` | **Date**: 2026-10-31 | **Spec**: `kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/spec.md`
**Input**: Mission specification from `kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/spec.md`; discovery in `research.md`

## Summary

Two activation writers still race `charter synthesize`/`resynthesize` without the run-wide synthesis lock
(#6453): (1) the `charter activate`/`deactivate` activation-config read-modify-write, and (2) the
activation-ledger migration's manifest stamp (`activation_ledger._stamp_manifest`). The fix takes the
**existing** `charter.activation.synthesizer.synthesis_lock.synthesis_lock()` around each writer's whole
read → plan → write window, at the seams every caller shares, and surfaces an unacquirable lock as the coded
refusal `CHARTER_SYNTHESIS_LOCK_HELD` / `CHARTER_SYNTHESIS_LOCK_UNAVAILABLE` with nothing written. No new
lock, no new lock path, no changed lock ordering.

## Technical Context

**Language/Version**: Python 3.11 (project floor; `from __future__ import annotations` everywhere touched)
**Primary Dependencies**: Typer (CLI), ruamel.yaml (round-trip activation writes), pydantic (synthesis manifest), `kernel.locks.machine_file_lock` (the lock primitive the synthesis lock already wraps)
**Storage**: files under `.kittify/` — the activation ledger `.kittify/charter/activation.yaml` (or legacy `config.yaml` / pointed `charter.yaml`), `synthesis-manifest.yaml`, and the lock file under `<git-common-dir>/spec-kitty-locks/charter-synthesis/<digest>.lock`
**Testing**: pytest; deterministic two-writer handshake (the #6453 `_Handshake` pattern) plus a cross-thread lock holder fixture; `monkeypatch` of `synthesis_lock._SYNTHESIS_LOCK_TIMEOUT_S` to keep refusal tests sub-second
**Target Platform**: Linux/macOS/Windows developer workstations and CI (POSIX and Windows lock primitives already handled by `kernel.locks`)
**Project Type**: single Python package (`src/charter`, `src/specify_cli`, `src/kernel`) with an architectural-test suite
**Performance Goals**: no measurable change to a single-writer command; an uncontended lock acquisition is one file open + `flock`, i.e. the same cost `restamp_bundle_hash` already pays per activation write
**Constraints**: bounded 10 s wait then refusal; re-entrant acquisition (nested synthesis inside `--resynthesize`); read-only runs take no lock; git unavailable ⇒ refuse rather than write unlocked
**Scale/Scope**: 4 write seams, 2 source files' worth of behaviour change, 1 new test module, 1 changelog entry, 3 docs touch-ups at most

## Charter Check

*GATE: passed before Phase 0; re-checked after Phase 1.*

- **Single canonical authority** — the lock, its placement and its timeout stay owned by
  `synthesis_lock`; the change adds callers, not a second mechanism (C-001, NFR-001).
- **ATDD-first / DIRECTIVE_034** — a failing two-writer test through the pre-existing entry points
  (`ActiveCharterManager.deactivate`, `append_synthesized_activations`, `apply_ledger_migration`) precedes
  the fix (`tests/charter/activation/test_activation_writes_under_synthesis_lock.py`).
- **Locality of change (DIRECTIVE_024) / smallest viable diff** — the edit lands in the four seams the issue
  names and in the two CLI commands' error rendering; no refactor of the activation engine, the resolver or
  the preset planner.
- **`__all__` convention** — no new public symbol is exported; the internal helpers stay module-private.
- **Campps cleaning / DIRECTIVE_025** — docstrings state the invariant ("the RMW is one unit under the
  lock") so the next writer does not re-open the race.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — targeted suites only (charter activation, presets, synthesis lock,
  activation ledger, migration).

## Project Structure

### Documentation (this mission)

```
kitty-specs/activation-writes-under-synthesis-lock-01M68ZS1/
├── plan.md              # This file
├── research.md          # Discovery: decisions, evidence, open questions
├── spec.md              # FR/NFR/C rows the WPs trace to
├── tasks.md / tasks/    # WP breakdown (/spec-kitty.tasks)
└── traces/              # tooling-friction.md, approach.md, design-decisions.md
```

### Source Code (repository root)

```
src/charter/activation/
├── synthesizer/synthesis_lock.py     # the lock (unchanged; the one authority)
├── pack_manager.py                   # ActiveCharterManager.activate/.deactivate  → take the lock
├── preset_application.py             # apply_preset_plan                          → take the lock
├── activation_engine.py              # promote_activations (shared append primitive) → take the lock
├── activation_ledger.py              # apply_ledger_migration (ledger write + _stamp_manifest + strips) → take the lock
└── bundle_restamp.py                 # precedent: already locks its manifest RMW (unchanged)

src/specify_cli/cli/commands/charter/
├── activate.py                       # positional activate + --preset: hold the window, render the lock refusal
└── deactivate.py                     # positional deactivate: hold the window, render the lock refusal

tests/charter/activation/
└── test_activation_writes_under_synthesis_lock.py   # new: the red-first two-writer + refusal tests
```

## Phase 0 — Research (complete)

`research.md` records the reproduction on `main` at `6f73b2a98e` (`precondition_changed`, deactivation lost),
the writer inventory, and the decisions D-01…D-04. Open question OQ-2 (any other writer?) is answered here:

| Writer of the activation config / manifest | Seam | Under the lock after this mission |
| --- | --- | --- |
| `charter activate KIND ID` (direct + cascade) | `ActiveCharterManager.activate` | yes (FR-001) |
| `charter deactivate KIND ID` (direct + cascade) | `ActiveCharterManager.deactivate` | yes (FR-001) |
| `charter activate --preset` | `plan_preset_application` + `apply_preset_plan` | yes (FR-002) |
| synthesis append (`reach_only._promote`) | `promote_activations` | yes (already; now self-guarding, FR-003) |
| interview/org-required promotion | `promote_activations` | yes (FR-003) |
| activation-ledger migration | `apply_ledger_migration` → `_stamp_manifest` | yes (FR-004) |
| compiled-catalog write (`compiler.write_compiled_charter`, mission-type provisioning) | post-write `recompile_or_notify` | **no** — declared out of scope (C-004): it is re-derived by the next synthesis run and is a staleness question, not a lost write |

## Phase 1 — Design

### Lock window placement

```
CLI activate/deactivate            manager / preset / promote / migration
────────────────────────           ─────────────────────────────────────
preflight (read-only, unlocked)    synthesis_lock(repo_root):
  ↓                                  read the activation target
synthesis_lock(repo_root):           plan (pure)
  read → plan → commit → restamp     write (precondition-guarded)
  (cascade children nest)            (restamp nests; re-entrant)
  ↓                                close
post-write recompile (unlocked,
  see C-004)
```

### Refusal rendering

`SynthesisLockHeldError` / `SynthesisLockUnavailableError` are `KittyInternalConsistencyError`s carrying
`code` + `body`. The two CLI commands convert them to `CodedRefusal` at the window boundary, so the existing
`render_refusal` → `render_coded_error` seam emits `Error (CHARTER_SYNTHESIS_LOCK_HELD): …` in text and the
canonical `{"error": {"code": …, "message": …}}` envelope under `--json`, with exit 1 and nothing written.

### Testing strategy (red-first)

1. `test_deactivate_racing_a_synthesis_append_keeps_both_writes` — deterministic two-writer handshake; fails
   on `main` with `precondition_changed` and no deny entry; passes after (positive control: the appended id
   is present).
2. `test_migration_manifest_stamp_keeps_a_concurrent_synthesis_entry` — the migration pauses between its
   manifest read and write while a synthesis run's manifest write (under the run-wide lock) lands; the entry
   is absent before the fix, present after.
3. `test_activate_and_deactivate_refuse_while_a_synthesis_run_holds_the_lock` — period-2 refusal test with
   `_SYNTHESIS_LOCK_TIMEOUT_S` shortened; asserts the code and byte-identical files.
4. `test_migration_refuses_while_a_synthesis_run_holds_the_lock` — same for `apply_ledger_migration`.
5. `test_preset_apply_holds_the_lock` — the preset path takes the window (refusal variant, same shape).

## Implementation Concern Map

| IC | Concern | Owns |
| --- | --- | --- |
| IC-01 | The lock window inside the shared write seams (`pack_manager`, `preset_application`, `activation_engine`, `activation_ledger`) | FR-001…FR-004 |
| IC-02 | The CLI window and the coded refusal rendering (`activate.py`, `deactivate.py`) | FR-001, FR-002, FR-005 |
| IC-03 | The red-first two-writer and refusal tests | FR-006, NFR-002, NFR-003 |
| IC-04 | Changelog + docs for the refusal codes | FR-005 (user-facing) |

## Risks

- **Deadlock by nested acquisition** — mitigated by the lock's documented re-entrancy and by a test that
  drives `deactivate --resynthesize` (synthesis inside the window).
- **A held lock turning a previously-fast command into a 10 s stall** — mitigated by the bounded wait being
  the existing #6453 policy for every writing run, and by refusing rather than queueing unboundedly.
- **Windows lock semantics** — untouched: the change adds callers to the existing primitive.
- **Test flakiness** — the handshake waits on a *provable* lock contention signal
  (`_LockCore.try_lock_once` returning `False`), not on a sleep; each thread has a hard join timeout.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| — (none) | — | — |
