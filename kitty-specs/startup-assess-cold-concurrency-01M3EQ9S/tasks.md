# Tasks: Concurrency-safe cold startup asset assessment

**Mission**: `startup-assess-cold-concurrency-01M3EQ9S` (GitHub #3998; closes the stale #4017)
**Planning base / merge target**: `issue-3998-startup-assess-cold-concurrency`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/startup-asset-escalation.md](contracts/startup-asset-escalation.md), [quickstart.md](quickstart.md)

## Decomposition note

The plan sketched three sequential WPs, but WP01 (red-first + tidy-first) and WP02 (the fix) would both own `src/specify_cli/runtime/asset_preparation.py`. `finalize-tasks` forbids overlapping `owned_files`, so they are merged into **one code WP**. That WP keeps the red-first discipline as **separate, ordered commits** (red test → tidy-first extraction → fix → flip). Closeout is its own `planning_artifact` WP. This is recorded in `tracer-design-decisions.md`.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first issue-pinned regression test through each owner's `ensure_*` (leaf `node_state` injection; peer finishes inside real lock) — commit RED | WP01 | |
| T002 | Tidy-first: extract `_serialize_owner(lock_paths, anchor)` from `recheck_assets` (behaviour-preserving commit) | WP01 | |
| T003 | `TornReadError(ValueError)` raised by `AssetPreparation.observe()` carrying path/role/lock_paths/anchor | WP01 | |
| T004 | `build_serialized(build, *, logger)` replaces `retry_torn_read`; retire `_TORN_READ_RETRY_ATTEMPTS` / `_TORN_READ_MESSAGE_PREFIX`; INFO operator signal | WP01 | |
| T005 | `incomplete()` distinct codes + swap the three owner call sites (bootstrap / agent_commands / agent_skills) | WP01 | |
| T006 | `StartupAssetError(GuardedReadError, RuntimeError)` raised by the three startup entry points (6 raise sites) | WP01 | |
| T007 | Primitive unit tests + C-008 lock-set identity + warm-path spy + Windows lock-read + ancestor-directory tests | WP01 | |
| T008 | Flip the regression test to a functional test; terminal / no-traceback CLI test (text + `--json`) | WP01 | |
| T009 | Blast-radius run, re-pin audit, ruff/format/mypy, complexity ≤ 15 | WP01 | |
| T010 | CHANGELOG `[Unreleased]` → `### Fixed` entry (#3998, #4017) | WP02 | [P] |
| T011 | Fresh-home reproducer evidence (N=16/32 ×5, one CPU-pinned) recorded in the mission | WP02 | [P] |
| T012 | Close the tracer files (approach / design-decisions / tooling-friction) | WP02 | [P] |

---

## WP01 — Torn-read escalation to the serialization point (red-first → fix)

**Goal**: A destination-role torn read on any owner's unlocked assessment waits on the owner's serialization point and reassesses once instead of crashing. Terminal startup failures render through the existing CLI error hook, with no traceback. The warm path is unchanged.
**Priority**: P1 (the whole defect). **Dependencies**: none.
**Independent test**: `pytest tests/runtime/test_startup_torn_read_escalation.py tests/runtime/test_build_serialized.py` is red on the planning base (entry-point tests) and green at WP tip.
**Requirements**: FR-001..FR-008, NFR-002..NFR-004, C-001..C-010.
**Prompt**: [tasks/WP01-torn-read-escalation.md](tasks/WP01-torn-read-escalation.md) (~520 lines)

Included subtasks:

T001 Red-first issue-pinned regression test through each owner's `ensure_*` (WP01)
T002 Tidy-first `_serialize_owner` extraction (WP01)
T003 `TornReadError` in `observe()` (WP01)
T004 `build_serialized` replaces `retry_torn_read`, plus INFO signal (WP01)
T005 `incomplete()` codes + three owner swaps (WP01)
T006 `StartupAssetError` at the startup entry points (WP01)
T007 Primitive / lock-set / warm / Windows / ancestor tests (WP01)
T008 Flip regression → functional; no-traceback CLI test (WP01)
T009 Blast radius, re-pin audit, quality gates (WP01)

**Implementation sketch**: commit T001 red → T002 (tidy-first, existing recheck tests green) → T003–T006 fix → T007–T008 tests → T009 gates.
**Risks**: a self-deadlock on re-entrant paths (C-005); a second lock authority (C-008); a warm-path regression (NFR-002); a source-drift relaxation (C-001). All are pinned by T007 tests.

---

## WP02 — Closeout: changelog, reproducer evidence, tracers

**Goal**: Record the user-facing fix in the CHANGELOG, capture the fresh-home reproducer evidence (NFR-001/SC-001), and close the three tracer files.
**Priority**: P2. **Dependencies**: WP01.
**Independent test**: CHANGELOG entry present under `[Unreleased]` → `### Fixed`. The evidence file shows 0 fresh-home failures across 10 runs.
**Requirements**: FR-009, NFR-001.
**Prompt**: [tasks/WP02-closeout-changelog-evidence.md](tasks/WP02-closeout-changelog-evidence.md) (~200 lines)

Included subtasks:

T010 CHANGELOG `[Unreleased]` entry (WP02)
T011 Fresh-home reproducer evidence (WP02)
T012 Tracer close (WP02)

**Parallel opportunities**: T010–T012 are independent of each other; all follow WP01.
**Risks**: running the reproducer against the wrong source tree (the global `spec-kitty` binary resolves the main checkout). The prompt pins a wrapper that runs the lane's `src`.
