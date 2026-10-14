# Mission Specification: CI uv-sync resilience for test-shard jobs

**Mission Branch**: `issue-6191-ci-uv-sync-resilience`
**Created**: 2026-10-13
**Status**: Draft
**Input**: GitHub issue #6191 — "CI: transient `uv sync` failure in the `tests (docs)` shard reds the required router gate"

## Overview

The `tests (docs)` module-test job in the **CI Router** workflow
(`.github/workflows/ci-router.yml`) intermittently fails at its dependency-install
step (`uv sync --frozen --all-extras`, which runs *before any test*). Because the
required **`router gate`** `needs:` that shard, one transient install hiccup reds
the whole gate and blocks merges on `main` and on every docs-selecting PR.

Evidence that this is a transient per-runner network-download failure, not a lock,
dependency, or code defect: `uv lock --check` passes on the same commits; a local
`uv sync --frozen --all-extras` on the same lock exits 0; and in the same CI Router
run ~8 sibling jobs run the identical `setup-uv@v10.0.1` + `uv sync --frozen
--all-extras` block and all succeed. Only the one `tests (docs)` job's install
fails.

This mission hardens the shared **module-test-shard** install so a single transient
download failure no longer reds the gate, applied consistently to the three
module-test shards that share the `setup-uv` → `uv sync --frozen --all-extras` →
`pytest` pattern: `tests-docs`, `tests-e2e`, `tests-corpus-blocking`. It is a
CI-infrastructure resilience fix on a **network-install step**, explicitly **not**
a test re-run and **not** a change to any dependency, lockfile, or gate semantics.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A transient install hiccup no longer blocks the merge gate (Priority: P1)

A maintainer opens (or lands) a docs-selecting change. On one CI runner the
`tests (docs)` shard's `uv sync` download drops a connection for the first attempt.

**Why this priority**: This is the whole point of the mission — one flaky download
must not red the required `router gate` and block an otherwise-green change.

**Independent Test**: With a stubbed `uv` that fails its first invocation and then
succeeds, the shard's install step completes successfully (exit 0), so the shard
and `router gate` stay green. Testable in isolation against the retry helper and
against the workflow wiring, with no real network.

**Acceptance Scenarios**:

1. **Given** the module-test-shard install step and a transient install failure on
   the first attempt, **When** the install runs, **Then** it retries (bounded) and
   succeeds, and the step exits 0.
2. **Given** a warm uv cache, **When** the shard's `setup-uv` runs with caching
   enabled, **Then** wheels are restored from cache rather than re-downloaded,
   reducing the download surface that can fail.

### User Story 2 - A genuine, deterministic install failure still reds the shard (Priority: P1)

A change really does break the environment (e.g. an inconsistency a `--frozen`
install cannot satisfy on any attempt).

**Why this priority**: The resilience must not green-wash a real failure. A
deterministic install error must still exhaust the bounded attempts and red the
shard, preserving the honest signal.

**Independent Test**: With a stubbed `uv` that fails on every attempt, the retry
helper returns the non-zero exit code after exhausting its bounded attempts, so the
step fails. Testable against the helper directly.

**Acceptance Scenarios**:

1. **Given** an install command that fails on every attempt, **When** the retry
   helper runs it with its bounded attempt cap, **Then** it exits non-zero with the
   underlying failure's exit code and does not report success.

### User Story 3 - Removing the resilience reds a focused guard (Priority: P2)

A future edit accidentally drops the cache input or the retry wrapper from a
module-test shard.

**Why this priority**: The resilience should be pinned so it cannot silently
regress; this is slice 3's done-when.

**Independent Test**: A `tests/ci/` wiring test parses `ci-router.yml` and asserts
each module-test shard keeps both the cache input and the retry-routed install;
removing either reds the test.

**Acceptance Scenarios**:

1. **Given** the hardened workflow, **When** the wiring test runs, **Then** it
   passes; **and** if `enable-cache: true` or the retry wrapper is removed from any
   of the three shards, the test fails.

### Edge Cases

- Happy path (install succeeds on the first attempt): the helper adds no retry and
  no backoff delay — one subprocess spawn, then straight through.
- All attempts fail: the step reds with the install's own exit code (no `|| true`,
  no `set +e`, no `exit 0` soft-fail).
- The retry wrapper's shell/argument handling must survive the workflow's
  `bash -n` syntax guard and the multi-line pytest command that follows it in the
  same shard `run:` block.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Bounded retry on transient install failure | As a maintainer, I want the module-test-shard `uv sync` to retry a transient download failure so that one network hiccup does not red the required gate. | High | Open | [build] | no — proven by a stub `uv` that fails once then succeeds; a single-attempt (no-retry) install fails that fixture |
| FR-002 | Cache-backed shard install | As a maintainer, I want the module-test shards' `setup-uv` to enable the uv cache so that wheels are restored instead of re-downloaded, shrinking the transient-failure surface. | Medium | Open | [build] | no — the wiring test asserts `enable-cache: true` on each shard; its absence reds the test |
| FR-003 | Deterministic failure is not masked | As a reviewer, I want a genuine, deterministic install failure to still red the shard after the bounded attempts so that resilience never green-washes a real defect. | High | Open | [build] | no — proven by a stub `uv` that fails every attempt; the helper must propagate the non-zero exit, so a swallow-errors impl fails the fixture |
| FR-004 | One shared helper, applied consistently | As a maintainer, I want the retry pattern implemented once in a shared helper and invoked identically from all three module-test shards so that the diff is minimal and consistent. | Medium | Open | [build] | no — the wiring test asserts all three shards (`tests-docs`, `tests-e2e`, `tests-corpus-blocking`) route `uv sync` through the same helper |
| FR-005 | Focused guard reds if resilience removed | As a maintainer, I want a focused `tests/ci/` assertion that fails if the cache input or the retry wrapper is removed from any shard so that the resilience cannot silently regress. | Medium | Open | [build] | no — the test is written to fail on a workflow with the resilience stripped (slice-3 done-when) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded, backed-off retry | The retry is capped at 3 total attempts with exponential backoff between attempts; happy-path (first-attempt success) adds zero backoff delay; worst-case added wall-clock from backoff is ≤ 15 seconds. | Performance | High | Open |
| NFR-002 | Clean, minimal helper | Any new Python helper passes `ruff check`, `ruff format --check`, and `mypy` with zero issues, has cyclomatic complexity ≤ 15, and uses only the Python standard library (it runs on the runner's default `python3`, before the venv is built). | Maintainability | High | Open |
| NFR-003 | Existing CI wiring stays green | The change keeps every pre-existing `tests/ci/` and `tests/architectural/` workflow-shape guard green, re-pointing honestly (never loosening) if any step text it asserts changes. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Gate semantics unchanged | Do not change `router gate`'s `needs:` set or the `scripts/ci/router_gate.py` classifier semantics; a shard only turns green when its install genuinely succeeds. | Technical | High | Open |
| C-002 | No dependency/selection change | Do not touch `uv.lock`, `pyproject.toml`, or any shard's pytest test selection/semantics; the retry re-attempts the same `--frozen` pinned install. | Technical | High | Open |
| C-003 | Network-install resilience, not test retry | No test re-run, retry plugin (`pytest-rerunfailures`, `flaky`), or `--reruns` is added; resilience applies only to the pre-test network-install step (flakiness-policy carve-out). | Technical | High | Open |
| C-004 | No new size/ratchet gates | Do not add any new size, length, or ratchet gate (operator ruling). | Business | Medium | Open |
| C-005 | Scope to the module-test shards | Edits are scoped to the `uv sync` / `setup-uv` of `tests-docs`, `tests-e2e`, `tests-corpus-blocking` plus one shared helper and its tests; the architectural battery, `tests-contract-tools`, `mission-state-audit`, and the shift-left/fast gates are out of scope. | Technical | Medium | Open |

### Key Entities

- **Module-test shard**: a CI Router job whose setup is `actions/checkout` →
  `astral-sh/setup-uv` → `uv sync --frozen --all-extras` → `pytest`. The three
  instances are `tests-docs`, `tests-e2e`, `tests-corpus-blocking`.
- **Retry helper**: the single shared `scripts/ci/` script that runs a given
  command with a bounded, backed-off retry and propagates the final exit code.
- **Router gate**: the terminal aggregator job that `needs:` every shard and
  blocks merge on a `failure`/`cancelled` dependency.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single transient `uv sync` download failure in a module-test shard
  no longer reds `router gate` — the install retries and the shard stays green —
  while a deterministic install failure still reds the shard. — [build] · no-op passable: no
- **SC-002**: All pre-existing `tests/ci/` workflow-shape guards and the new focused
  resilience guard pass; none were loosened to achieve it. — [build] · no-op passable: no
- **SC-003**: The resilient install pattern is defined exactly once (one shared
  helper) and invoked identically by all three module-test shards; the diff touches
  no lockfile, `pyproject.toml`, gate `needs:`, or pytest selection. — [ratchet] · no-op passable: no
