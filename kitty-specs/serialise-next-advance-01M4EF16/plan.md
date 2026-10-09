# Implementation Plan: Serialise concurrent next advance

**Branch**: `issue-5854-serialise-next` | **Date**: 2026-10-08 | **Spec**: `kitty-specs/serialise-next-advance-01M4EF16/spec.md`
**Input**: Mission specification from `kitty-specs/serialise-next-advance-01M4EF16/spec.md`

## Summary

Make advancing a mission run serialised (closes #5854, #5682). Two complementary
mechanisms, both load-bearing (established by the pre- and post-spec squads in
`research.md`):

1. **Expected-step compare-and-swap** — thread the caller's bootstrap-evaluated
   `issued_step_id` into the advance and refuse when the run's issued step changed
   before commit. This closes the bootstrap→plan staleness window (#5682) on both
   the composition and engine paths. **It is folded into the existing
   `commit_advance` / `StaleAdvancePlan` staleness authority (widened window), not
   a new parallel bridge gate** (doctrine-daphne note 1).
2. **Per-run-dir lock** — a dedicated `<run_dir>/state.json.lock` via
   `kernel.locks.machine_file_lock`, held only around the commit read-modify-write
   (never across executor dispatch). This closes the true-concurrency TOCTOU where
   two writers both pass the CAS and both append. It wraps `_commit_advance`,
   `provide_decision_answer`, and the retrospective-rollback writer.

Plus: the engine path refuses a stale plan with a `blocked` Decision (mirroring
composition's EDGE-003) and catches `LockAcquireTimeout`, instead of re-planning
`success` via `next_step` (#5854's second half); snapshot writes use a unique temp
name; a new 4.x ADR records the writer model.

Full root-cause analysis, adjudicated design, writer inventory, prior-art tests
and squad dispositions live in `kitty-specs/serialise-next-advance-01M4EF16/research.md` —
this plan does not duplicate them.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `kernel.locks.machine_file_lock` (the one canonical cross-process lock primitive); `kernel.atomic` (unique-temp atomic write). No new third-party dependencies.
**Storage**: per-run files under `.kittify/runtime/runs/<run_id>/` — `state.json` (run cursor) and `run.events.jsonl` (append-only event journal).
**Testing**: pytest; deterministic concurrency reproductions via injected interleaves (`monkeypatch`) and `threading.Barrier`, never sleeps; markers `p0_repro(issue=…)`/`regression` (per-PR) and `stress` (parallel-unsafe true-concurrency proof, nightly/serial).
**Target Platform**: cross-platform CLI (Linux, macOS, Windows 10+); the lock primitive is fcntl on POSIX, msvcrt on Windows.
**Project Type**: single (CLI/runtime library).
**Performance Goals**: an uncontended `next` adds exactly one lock acquire/release to the advance; typical-project CLI budget < 2 s preserved (informational).
**Constraints**: the runtime layer must not import `specify_cli` (layer rules, C-001); all locking routes through `kernel.locks` (DIRECTIVE_043, empty-allowlist gate); lock span structurally excludes executor dispatch (NFR-001).
**Scale/Scope**: one run cursor per mission run; fix confined to `src/runtime/next/` + `src/kernel/` + one ADR + one doc update.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (#1)** — PASS. The run-cursor lock is a distinct
  resource over the ONE `kernel.locks` primitive (not a second authority beside
  the run-index lock); the CAS extends `commit_advance`'s `StaleAdvancePlan` rather
  than adding a parallel staleness check. (doctrine-daphne, post-spec: PASS.)
- **DIRECTIVE_043 single canonical locking primitive** — PASS. No raw
  fcntl/msvcrt/`filelock`; `test_lock_primitive_ban.py` empty allowlist stays
  empty (NFR-003).
- **Architectural alignment / layer rules** — PASS. Fix lives in runtime+kernel;
  no `specify_cli` import (C-001); `test_layer_rules.py` targeted.
- **ATDD-first (C-011)** — three deterministic red-first reproductions are the
  executable contract; each fix part is independently pinned (spec SC-003).
- **Terminology canon** — PASS (zero `feature` introductions; legacy
  `feature-runs.json` left frozen).
- **Supply-chain (DIRECTIVE_051)** — N/A: no dependency is added, upgraded, or
  removed.
- **Contract authority** — refusals reuse ADR `2026-02-17-1`'s `next` contract
  (`kind=blocked` + reason, exit 1); no new kind/exit (FR-005).

No charter violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/serialise-next-advance-01M4EF16/
├── plan.md              # This file
├── research.md          # Root cause + adjudicated design + squad dispositions
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output (how to verify)
├── traces/              # Mission tracer files
├── spec.md
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

(No `contracts/` — this mission defines no new interface; `meta.json` carries
`"contracts": "none"` with a rationale so strict `accept` waives the requirement.)

### Source Code (repository root)

```
src/runtime/next/_internal_runtime/engine.py   # CAS into plan_advance/commit_advance;
                                                # lock around _commit_advance + provide_decision_answer;
                                                # unique-temp _write_snapshot
src/runtime/next/runtime_bridge.py             # _dn_advance_engine refuses (blocked) + catches
                                                # LockAcquireTimeout; thread bootstrap step; lock the
                                                # retrospective-rollback writer (_dn_rollback_buffered_run_state)
src/runtime/next/runtime_bridge_engine.py      # commit leg carries the expected step through
src/runtime/next/run_lock.py (new, run_index-style) # the per-run-dir lock helper (path + machine_file_lock)
src/kernel/atomic.py                           # (reuse) unique-temp atomic write

tests/next/        # bridge-level repros (composition window, engine inversion, answer race)
tests/runtime/     # engine-level + true-concurrency barrier (stress) repro
docs/adr/4.x/      # new ADR: run-dir writer model
docs/architecture/runtime-loop.md  # state the shipped serialisation guarantee
```

**Structure Decision**: single-project runtime fix. The lock path/constructor
goes in a small new `run_lock.py` helper next to `run_index.py` (same pattern:
dedicated `.lock` sidecar, blocking acquire with timeout), so the lock resource
has one owning module; the CAS and lock *usage* stay in `engine.py` with minimal
`runtime_bridge*.py` call-site churn (C-003, pending the unmerged sibling branch).

## Complexity Tracking

*No Charter Check violations — not applicable.*

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Expected-step compare-and-swap (close the #5682 window)

- **Purpose**: Refuse an advance whose run cursor changed since the caller
  evaluated its step, on both composition and engine paths.
- **Relevant requirements**: FR-001, FR-002 (engine half), SC-001, SC-002.
- **Affected surfaces**: `engine.py` (`plan_advance`, `commit_advance`,
  `StaleAdvancePlan` — widen to carry/compare the bootstrap `issued_step_id`);
  `runtime_bridge.py` (thread `ctx.current_step_id` into the plan/commit);
  `runtime_bridge_engine.py` (carry the expected step through the composition
  commit leg).
- **Sequencing/depends-on**: none (foundational).
- **Risks**: must EXTEND the existing `StaleAdvancePlan` authority, not add a
  parallel check (doctrine-daphne note 1). Keep call-site churn minimal (C-003).

### IC-02 — Per-run-dir lock + unique temp (close the true-concurrency TOCTOU)

- **Purpose**: Serialise the run-cursor read-modify-write so two writers cannot
  both pass the CAS and both append; give snapshot writes a unique staging file.
- **Relevant requirements**: FR-003, FR-004, FR-006, NFR-001, NFR-002, NFR-003,
  SC-003 (lock + temp parts).
- **Affected surfaces**: new `run_lock.py` (lock path + `machine_file_lock`
  constructor, run_index-style); `engine.py` `_commit_advance`,
  `provide_decision_answer`, `_write_snapshot` (unique temp via `kernel.atomic`);
  `runtime_bridge.py` `_dn_rollback_buffered_run_state` (+ its capture) under the
  same lock.
- **Sequencing/depends-on**: pairs with IC-01 (CAS is re-checked under this lock).
- **Risks**: lock held ONLY around the commit, never across executor dispatch
  (NFR-001); index-lock released before this lock (C-002, no deadlock); the
  rollback writer is deleted by the unmerged sibling `issue-5883-*` — cover it on
  current main, drop coverage if the sibling lands first.

### IC-03 — Engine-path refusal (close #5854's second half)

- **Purpose**: The engine path returns a `blocked` Decision on a stale plan and a
  lock timeout, never re-planning `success` through `next_step`.
- **Relevant requirements**: FR-002, FR-005.
- **Affected surfaces**: `runtime_bridge.py` `_dn_advance_engine` (catch
  `StaleAdvancePlan` AND `LockAcquireTimeout` → `blocked` via the EDGE-003 shape;
  remove the `runtime_next_step` fallback). Invert the existing pin
  `test_pre_resolution_is_not_reused_for_a_different_issued_step` (keep, don't
  delete).
- **Sequencing/depends-on**: IC-01.
- **Risks**: reuse the existing `blocked`/exit-1 contract (FR-005) — no new kind.

### IC-04 — ADR + doc (record the writer model)

- **Purpose**: Capture the cross-process run-dir writer model as a decision record
  and state the shipped guarantee where the multi-agent loop is advertised.
- **Relevant requirements**: supports the Single-Canonical-Authority principle.
- **Affected surfaces**: new `docs/adr/4.x/<date>-<n>-serialise-run-dir-advance.md`
  (cross-reference ADR `2026-02-17-1` for the `blocked` contract reuse and cite the
  run-index lock as same-primitive precedent — doctrine-daphne note 2);
  `docs/architecture/runtime-loop.md` ("multiple agents … in parallel" → state the
  serialisation guarantee).
- **Sequencing/depends-on**: after IC-01..IC-03 land conceptually.
- **Risks**: keep the ADR short; it documents an application of existing patterns.

### IC-05 — Deterministic red-first acceptance suite (the gate)

- **Purpose**: Pin every independent fix part so none ships untested (SC-003).
- **Relevant requirements**: SC-001..SC-004, every FR's non-vacuity control.
- **Affected surfaces**: `tests/next/` (composition-window repro, engine
  inversion, answer-vs-next race, contract-shape ratchet, unique-temp collision
  pair, held-lock-blocks deterministic lock proof); `tests/runtime/`
  (barrier-synchronised true-concurrency advance/advance — `stress`). Reuse
  fixtures `test_engine_commit_primitives.py::_start`,
  `_next_mission_scaffold.scaffold_software_dev`/`advance_to_step`,
  `test_provide_decision_answer_characterisation.py::_input_run`.
- **Sequencing/depends-on**: the red-first tests precede their fix parts (ATDD).
- **Risks**: each test must be red when ONLY its part is reverted (half-by-half);
  the lock is pinned by a deterministic held-lock-blocks test (per-PR) PLUS the
  barrier test (nightly), not by the barrier alone (reviewer-renata).
