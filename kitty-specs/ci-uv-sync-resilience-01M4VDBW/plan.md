# Implementation Plan: CI uv-sync resilience for test-shard jobs

**Branch**: `issue-6191-ci-uv-sync-resilience` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/ci-uv-sync-resilience-01M4VDBW/spec.md`

## Summary

Harden the shared module-test-shard install in `.github/workflows/ci-router.yml`
so a single transient `uv sync` download failure no longer reds the required
`router gate`. Mechanism (both legs of the issue's proposed remediation):

1. **Cache** — add `enable-cache: true` to the `astral-sh/setup-uv` step of the
   three module-test shards so wheels are restored from cache, shrinking the
   download surface that can transiently fail.
2. **Bounded retry** — route each shard's `uv sync --frozen --all-extras` through
   a single shared stdlib-only Python helper, `scripts/ci/uv_sync_retry.py`, that
   runs the command with ≤3 attempts and exponential backoff, propagating the
   final non-zero exit code so a deterministic failure still reds the shard.

The pattern is written once (one helper) and invoked identically from
`tests-docs`, `tests-e2e`, `tests-corpus-blocking`. Nothing about `router gate`'s
`needs:`/classifier, `uv.lock`, `pyproject.toml`, or any pytest selection changes.

## Technical Context

**Language/Version**: Python 3.11+ (helper runs on the runner's default `python3`, stdlib only, before the venv exists); GitHub Actions YAML (`.github/workflows/ci-router.yml`).
**Primary Dependencies**: None added. Helper uses `subprocess`, `sys`, `time` (stdlib). `astral-sh/setup-uv@v10.0.1` (unchanged pin) gains the `enable-cache` input.
**Storage**: N/A (the uv cache is GitHub Actions' standard action cache, managed by `setup-uv`).
**Testing**: pytest under `tests/ci/` — a wiring test (`test_uv_sync_resilience.py`) parsing `ci-router.yml`, and a helper unit test (`test_uv_sync_retry.py`) with a stubbed command.
**Target Platform**: `ubuntu-24.04` GitHub-hosted runners.
**Project Type**: single (CI infrastructure + test tooling).
**Performance Goals**: happy path adds zero backoff; worst-case backoff ≤ 15 s (NFR-001).
**Constraints**: mypy/ruff-clean, complexity ≤ 15, stdlib-only (NFR-002); no dependency/selection/gate change (C-001/C-002); no test-retry plugin (C-003); no new ratchet gates (C-004); scope limited to the three shards + helper + tests (C-005).
**Scale/Scope**: ~3 small YAML job edits, 1 new helper (~40 LOC), 2 new test modules.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Standing Order #4 (test-remediation / never retry-to-green)** — RESPECTED. The
  "never retry-to-green" rule governs *test* reruns that mask regressions
  (`docs/development/testing/testing-flakiness.md`). This mission adds resilience
  to a **network-install step that runs before any test**; it adds no
  `pytest-rerunfailures`/`flaky`/`--reruns`, and FR-003 proves a deterministic
  install failure still reds. Carve-out recorded in the grounding note §5.
- **Standing Order #5 (architectural gate discipline)** — RESPECTED. No new gate,
  allowlist, or ratchet is added (C-004). The new `tests/ci/` assertions are
  focused wiring/behavior tests, not a mutable-allowlist gate.
- **Standing Order #2 (campsite / smallest-viable-diff + locality)** — RESPECTED.
  Edits confined to the three module-test shards plus one shared helper; the
  architectural battery and other `uv sync` jobs are deliberately out of scope
  (C-005), with the boundary justified in the grounding note §1.
- **ATDD-First (C-011)** — PLANNED. Each WP commits its failing-first test before
  implementation (red on base, green on final).
- **Terminology Canon** — N/A to this CI change (no Mission/Feature-named surface
  touched); the terminology guard is unaffected.
- **NO_FULL_HEAVY_SUITES_IN_MISSION** — RESPECTED. Validation runs `tests/ci/`
  (owning dir) plus the specific named workflow-shape guard files, never a bare
  `tests/architectural/` sweep.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-uv-sync-resilience-01M4VDBW/
├── spec.md
├── plan.md                 # this file
├── research/
│   └── code-grounding.md   # committed pre-spec
├── checklists/requirements.md
└── tasks.md                # /spec-kitty.tasks output
```

### Source Code (repository root)

```
.github/workflows/ci-router.yml   # EDIT: 3 module-test shards (setup-uv enable-cache + retry-routed uv sync)
scripts/ci/uv_sync_retry.py       # NEW: shared bounded-retry install helper (stdlib-only)
tests/ci/test_uv_sync_retry.py    # NEW: helper unit test (retry/backoff/exit-code propagation)
tests/ci/test_uv_sync_resilience.py  # NEW: wiring test (cache + retry present on all 3 shards)
```

**Structure Decision**: Single-project CI tooling. The helper lives under
`scripts/ci/` (a namespace package: tests `from scripts.ci import uv_sync_retry`;
CI invokes `python3 scripts/ci/uv_sync_retry.py uv sync --frozen --all-extras`,
mirroring the existing `green_match.py`). Its tests live in `tests/ci/`, the
owning directory for CI wiring.

## Design decisions (from grounding)

- **Why a helper, not an inline bash loop**: the brief prefers the resilient
  pattern written *once*; a Python helper is unit-testable (FR-001/FR-003),
  mypy/ruff-clean, and complexity-bounded (NFR-002). It is invoked identically
  from all three shards (FR-004).
- **Why also `enable-cache`**: a cold cache still downloads, so caching is a
  *reducer* of the transient-failure surface, not a guarantee; the bounded retry
  closes the residual window. Both legs together match the issue's "cache and/or
  retry" remediation. No wiring test inspects the three shards' setup-uv `with:`
  block, so the input adds with zero re-pointing (grounding §3).
- **Why not a composite action / why architectural battery is out of scope**:
  converting inline `uv sync` to a composite `uses:` would break the
  `run_contains="uv sync"` finders in `test_ci_module_wiring.py` /
  `test_ci_workflow_prestep_shape.py` that cover the architectural jobs; keeping
  the change inline and scoped to the three shards needs no re-point (grounding §3).
- **No soft-fail idioms**: the retry helper must exit non-zero on exhausted
  attempts (FR-003); no `|| true` / `set +e` / `exit 0`.
- **Shell-syntax guard**: the shard `run:` block (helper call + multi-line pytest)
  must pass `tests/ci/test_workflow_run_shell_syntax.py` (`bash -n`, single `\`
  continuations).

## Implementation Concern Map

### IC-01 — Shared bounded-retry install helper

- **Purpose**: Provide one stdlib-only, tested helper that runs a command with a
  bounded, backed-off retry and propagates the final exit code.
- **Relevant requirements**: FR-001, FR-003, NFR-001, NFR-002, C-003.
- **Affected surfaces**: `scripts/ci/uv_sync_retry.py`, `tests/ci/test_uv_sync_retry.py`.
- **Sequencing/depends-on**: none (foundation for IC-02).
- **Risks**: must be importable as `scripts.ci.uv_sync_retry` (namespace package) and
  runnable by path; must not depend on the venv (stdlib only).

### IC-02 — Wire resilience into the three module-test shards + pin it

- **Purpose**: Add `enable-cache: true` to each shard's `setup-uv` and route each
  `uv sync` through the helper; add a wiring test that reds if either is removed.
- **Relevant requirements**: FR-002, FR-004, FR-005, NFR-003, C-001, C-002, C-004, C-005.
- **Affected surfaces**: `.github/workflows/ci-router.yml` (jobs `tests-docs`,
  `tests-e2e`, `tests-corpus-blocking`), `tests/ci/test_uv_sync_resilience.py`.
- **Sequencing/depends-on**: IC-01 (the helper must exist before shards invoke it).
- **Risks**: keep the shard `run:` bash valid (`bash -n` guard); do not disturb
  `router-gate.needs` or the routing-authority guards; do not touch the
  architectural battery or other `uv sync` jobs.
