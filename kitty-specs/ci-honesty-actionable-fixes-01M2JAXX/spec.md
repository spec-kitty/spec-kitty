# Mission Specification: CI Pipeline Honesty — Actionable Fixes

**Mission Branch**: `fix/ci-honesty-actionable-fixes`
**Created**: 2026-09-15
**Status**: Draft
**Epic**: #4437 · **Milestone**: 4.0.0 · **Priority**: P1
**Input**: Bundle four settled, independently-safe CI-honesty fixes (#4360-B, #4454, #4208, #4212) from epic #4437. Research + `file:line` evidence in `work/ci-honesty-4437/`.

## Overview

Spec Kitty's agent fleet relies on CI as the release authority: **green must mean actually-proven, red must mean a real regression** (ADR `2026-07-17-1-red-main-is-honest-ci-is-release-authority`). Four independent, settled cases break that contract today. Each is fixed RED-first, each is independently shippable, and — the binding invariant — **no fix may widen the green path**.

The coupled main-tip fan-out cluster (#4347 / #4371 / #4360-A / #4430) is deliberately **out of scope** here; it is being handled through a separate design ADR (`work/ci-honesty-4437/DRAFT-ADR-ci-main-verdict-topology.md`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diff-scoped PR is not falsely failed by the aggregate (#4360-B) (Priority: P1)

A maintainer opens a PR that touches one module. The diff-scoped matrix runs only that module's shard(s); every selected shard passes. Today the aggregate demands all registry shards (currently 37), finds the unselected ones absent with no eligible stale-fallback, and hard-fails "N registry-expected shards missing" — a **false-red on green work** (live repro: PR #4448 head `95d76daf`, aggregate run `34950420326`).

**Why this priority**: Live and biting on real PRs right now; blocks legitimate merges and erodes trust in the gate.

**Independent Test**: Extract the inline reconciler and unit-test it: `selected={M}`, current run has `M`, previous run empty → `complete=True, missing=[]` (RED today: `missing=[36]`).

**Acceptance Scenarios**:

1. **Given** a diff-scoped run that selected only module M and produced M's fresh coverage artifact, and no eligible previous run exists, **When** the shard reconciler computes completeness, **Then** the run is complete and no shard is reported missing.
2. **Given** a diff-scoped run that selected module M, **When** M's own shard artifact is absent from the current run, **Then** the reconciler still reports M missing and fails (the `must_be_fresh` guard holds — no false-green).
3. **Given** a full-mode run (`selected` is None / all registry modules), **When** the reconciler runs, **Then** the legacy all-registry backfill behaviour is unchanged.

---

### User Story 2 - A tests-only change runs its own tests (#4454) (Priority: P1)

A maintainer changes only files under `tests/<module>/**`. Today `select_modules` matches only `src/**` router globs, so the diff selects no module, the module-test matrix is empty, the changed tests never run per-PR — yet the PR goes **green**. A test edit that would fail is invisible until the nightly full run.

**Why this priority**: A false-green in a fleet that lands many PRs; a changed test that no longer passes can merge unnoticed.

**Independent Test**: `select_modules(["tests/status/test_store.py"])` returns the owning module set (RED today: returns `[]`).

**Acceptance Scenarios**:

1. **Given** a diff confined to `tests/status/**`, **When** the router selects modules, **Then** the `status` module (and the same group set a `src/specify_cli/status/**` change selects) is selected and its shards run.
2. **Given** a diff confined to `tests/ci/**`, **When** the router selects modules, **Then** the `ci` module is selected.
3. **Given** a diff confined to `tests/docs/**` or `tests/e2e/**` (already routed to dedicated path jobs), **When** the router selects, **Then** those paths do not additionally trigger a duplicate module lane.

---

### User Story 3 - A timeout-killed job is distinguishable from an external cancel (#4208) (Priority: P2)

When a shard hits its `timeout-minutes` ceiling, GitHub reports it as `cancelled` — identical to an externally-cancelled job — and the `router-gate` folds both into the same blocking set as `failure`. A maintainer cannot tell a slow-shard timeout from a real cancel without reading raw job logs.

**Why this priority**: Costs triage time on every ceiling-creep kill; classification honesty, not a verdict change.

**Independent Test**: A `timed_out`-aware classification helper reports `{tests-cli: timed_out, tests-e2e: failure}` distinctly (RED today: no such distinction exists).

**Acceptance Scenarios**:

1. **Given** a blocking job whose true jobs-API conclusion is `timed_out`, **When** the router-gate classifies the blocking set, **Then** the reported summary labels it `timed_out`, distinct from `cancelled` and `failure`.
2. **Given** the historical `{tests-cli: cancelled, tests-e2e: cancelled}` signature, **When** the gate evaluates, **Then** the blocking decision (pass/fail) is byte-for-byte identical to today's — the blocking policy is unchanged.

---

### User Story 4 - The nightly suite fails loud on a red suite (#4212) (Priority: P2)

The nightly `performance-and-e2e` (and interpreter-matrix) steps run under `set +e` and end on `echo "…exit=$?"`, discarding pytest's exit code; the job stays green even when a suite is red. A maintainer reading the nightly sees green while a real regression sits unreported.

**Why this priority**: Nightly-only (off the per-PR blocking path), but a silently-red nightly defeats the whole safety-net purpose.

**Independent Test**: The workflow-lint guard asserts each `pytest` suite step's exit is consumed by a step/job that can `exit 1` (RED today: the code is discarded into an annotation string).

**Acceptance Scenarios**:

1. **Given** a nightly run where the performance suite exits non-zero, **When** the job completes, **Then** the job result is `failure`, not `success`.
2. **Given** a nightly run where an earlier suite fails, **When** later suites run, **Then** every suite still runs (run-all `if: always()` / `fail-fast: false` preserved) and the job fails at the end.

### Edge Cases

- A diff-scoped run that selects **zero** modules (e.g. a docs-only change): the reconciler must not fabricate a false-red nor a false-green — unchanged always-on gates decide.
- A tests-only change touching a module that maps to **multiple** groups: select the identical group set a src change to that module hits (no narrowing to one "owning" module).
- A job that is BOTH failed and later cancelled: `timed_out` classification must not mask a genuine `failure`.
- A nightly suite that is skipped (marker-empty) vs. failed: skipped is not a failure.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Aggregate completeness requires only SELECTED shards fresh | As a maintainer, I want a diff-scoped PR whose selected shards all pass to be reported complete, so that green work is not falsely failed. | High | Open |
| FR-002 | Unselected shards backfill-if-available, never fatal when absent | As a maintainer, I want unselected shards to be optional (backfilled from a prior run if present, ignored if not), so that the aggregate does not demand shards the matrix intentionally skipped. | High | Open |
| FR-003 | Shard reconciler extracted to an importable, tested module | As a maintainer, I want the inline aggregate reconciler moved to `scripts/ci/reconcile_shards.py`, so that its completeness logic is unit-testable. | High | Open |
| FR-004 | Tests-only diff selects its owning module | As a maintainer, I want a `tests/<module>/**` (and `tests/ci/**`) change to select the same module group set a `src/**` change does, so that a tests-only PR runs the tests it changed. | High | Open |
| FR-005 | Router-gate reports timeout distinctly from cancel/failure | As a maintainer, I want a timeout-killed job classified as `timed_out` (via the jobs-API conclusion), distinct from external-cancel and failure, so that I can attribute a red without reading raw logs. | Medium | Open |
| FR-006 | Nightly fails loud when any suite exits non-zero | As a maintainer, I want the nightly job to fail when any suite is red, while still running every suite, so that a red nightly is never reported green. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No fix widens the green path | Zero of the four fixes introduces a new green path: a SELECTED-absent shard (FR-002) remains fatal, and the #4208 blocking decision is byte-identical to baseline for `{failure, cancelled}` inputs — both proven by a regression test in this mission. | Reliability | High | Open |
| NFR-002 | RED-first ATDD evidence | Each of the four fixes ships ≥1 test that is RED on base sha `36d866d4fa` and GREEN on the fix commit; new-code coverage ≥ 90%. | Testability | High | Open |
| NFR-003 | Zero lint/type regressions | All new/changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero issues; no new `# noqa` / `# type: ignore` / per-file ignores. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Cluster mechanisms untouched | Do NOT modify the coupled cluster: `ci-router.yml` concurrency stanza (`:35-37`, #4347), `ci-fleet-verdict.yml` fan-out (#4371), the aggregate main-ledger stale-fallback source query (#4360-A), or `fleet_verdict.py` terminal-cancel classification (#4430). Also untouched: #4374, #4420, #4429. | Technical | High | Open |
| C-002 | Preserve the two-authority router contract | #4454 adds `tests/<module>/**` globs to the hand-authored router filter groups (Option 1, single-authority); it must NOT introduce a second test-dir→module map (`contracts/router-two-authority.md`). | Technical | High | Open |
| C-003 | Preserve existing fail-closed / run-all guards | Keep the aggregate fail-closed guard (`ci-aggregate.yml:376-381`) and the nightly run-all semantics (`if: always()` / `fail-fast: false`); the fixes change eligibility/classification, never soften a guard. | Technical | High | Open |
| C-004 | Self-referential CI changes verified on the merged tip | Workflow-topology changes cannot be fully proven on the PR head alone; the mission must state how each is verified on the merged `main` tip ("a gate never run is not a gate"). #4454 and #4208 both edit `ci-router.yml` (different regions) — sequence to avoid collision. | Process | Medium | Open |

### Key Entities

- **Selected shard set**: the module shards the diff-scoped matrix chose for a given run (vs. the full registry shard set).
- **`must_be_fresh` guard**: the aggregate seam that keeps a SELECTED shard fatal-if-absent — the load-bearing false-green guard.
- **Router filter groups**: the two hand-authored routing authorities `select_modules` parses (`ci-router.yml` dorny filters + registry inventory).
- **Jobs-API `conclusion`**: the per-run field (`timed_out`, `failure`, …) that the `needs` context drops but the fix reads.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A diff-scoped PR whose selected shards all pass reports the aggregate complete with zero "registry-expected shards missing" (the PR #4448 shape passes).
- **SC-002**: A tests-only PR (`tests/<module>/**`) produces a non-empty module-test matrix that runs the owning module's shards.
- **SC-003**: A timeout-killed job is reported `timed_out` distinctly at the gate summary while the pass/fail blocking decision is unchanged from baseline.
- **SC-004**: A nightly run containing a failing suite reports the job as `failure` (not `success`), with every suite still executed.
