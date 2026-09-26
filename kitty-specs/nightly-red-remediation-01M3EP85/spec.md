# Mission Specification: Nightly red remediation (run 36225024230)

**Mission Branch**: `claude/lucid-ptolemy-fjtzep`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Brief intake — review-squad remediation analysis on spec-kitty#5045 ([comment](https://github.com/spec-kitty/spec-kitty/issues/5045#issuecomment-5844901490)), analysed on `main` @ `ae0ff2fbf2da024b40e81afe2bca515e37c7f4b7`. Scope confirmed by the operator (Decision Moment `01M3EP8GQWCEAWKGMBVQYNFN65`).

## Context

The first nightly run of the `integration-next` lane (CI Nightly run 36225024230) went red with 25 failures. The performance suite had 2 failures, and the Python 3.13 interpreter leg hit its job timeout. That timeout left no escalation issue and no failing summary. The review squad classified the causes as follows:

- 25 integration failures: seven fixture drifts, each left behind by a deliberate product change.
- 2 real product defects in the merge command.
- 1 gap in the CI escalation safety net.
- 1 mis-aimed performance gate.

This mission turns the nightly honestly green: every change is either a justified test re-pin (the product contract moved on purpose) or a product/CI fix proven red-first.

Addressed: #5045 (integration suite red), #5049 (performance suite red).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintainer reads an honest nightly (Priority: P1)

A maintainer opens the nightly results after a merge day. Every failure it reports is a real defect, not stale test scaffolding left behind when a product contract changed on purpose.

**Why this priority**: A suite that is red for stale reasons hides real regressions and cannot ever be promoted to a per-PR gate (#5037).

**Independent Test**: Run the integration and next test directories locally; the 25 previously failing tests pass, and each updated test still asserts the current product contract.

**Acceptance Scenarios**:

1. **Given** the coordination read fails closed on an unmaterialized coordination worktree (ADR 2026-09-24-2), **When** the surface-seam and split-brain tests run, **Then** they assert the fail-closed refusal rather than a fallback to the primary checkout.
2. **Given** merge now requires a reconciliation claim, **When** merge tests that fake git and the lanes manifest run, **Then** they exercise their own concern (index refresh, untracked tolerance, sparse invariant, resume bookkeeping) without being refused by the reconciliation gate.
3. **Given** the arbiter-override review fixture, **When** it lacks a lanes manifest, **Then** a dedicated test proves the task-move guard still refuses. **When** the manifest is present, the arbiter override tests pass.
4. **Given** a rejection followed by rework and approval, **When** the retrospect smoke test runs, **Then** the approval is seeded causally and a retrospective record is created.

---

### User Story 2 - Operator previews a merge on a mission whose coordination worktree is not checked out (Priority: P2)

An operator runs `spec-kitty merge --dry-run` on a mission that declares a coordination branch whose worktree has not been materialized yet.

**Why this priority**: Today the command crashes with a raw Python traceback. A real merge in the same situation fails cleanly with guidance.

**Independent Test**: Invoke the dry-run on such a mission. It exits non-zero with the same actionable guidance the real merge prints, in both human and JSON output modes.

**Acceptance Scenarios**:

1. **Given** an unmaterialized coordination worktree, **When** the operator runs `merge --dry-run`, **Then** they see the unmaterialized-coordination message and the materialize hint, the exit code is 1, and no traceback is printed.
2. **Given** the same state with `--json`, **When** the operator runs the dry-run, **Then** stdout is a single JSON error document.

---

### User Story 3 - Operator re-runs a merge that stopped at a pre-flight gate (Priority: P2)

An operator starts a fresh `spec-kitty merge`. It stops before any lane is consolidated: merge gates failed, the history guard refused, or the operator declined the hollow-review confirmation. The operator fixes the cause and runs `spec-kitty merge` again.

**Why this priority**: If the re-run is refused as a "pre-fix in-flight merge", the only way out is `--abort` plus manual verification, for a merge that never mutated anything.

**Independent Test**: Force a fresh merge to stop at one of those exits, then run a plain merge again; it proceeds and does not report a pre-fix state.

**Acceptance Scenarios**:

1. **Given** a fresh merge that stopped before consolidation, **When** the operator re-runs a plain merge, **Then** it is not refused as a pre-fix merge.
2. **Given** a genuinely pre-fix in-flight merge state (created before the reconciliation marker existed), **When** a merge resumes it, **Then** it is still refused as today.
3. **Given** a merge state that is aborted or cleared, **When** the operator starts again, **Then** no stale reconciliation marker survives.

---

### User Story 4 - Maintainer is paged when a nightly interpreter leg overruns (Priority: P2)

The Python 3.13 interpreter leg takes longer than its time cap.

**Why this priority**: Today the job is killed, its escalation step never runs, no P0 is filed, and the nightly summary stays green. The red is invisible.

**Independent Test**: Workflow-shape tests over the nightly workflow prove that the suite step is bounded inside the job cap, that the escalation and fail-loud steps run after an overrun, and that the summary fails on any non-success leg.

**Acceptance Scenarios**:

1. **Given** the interpreter suite overruns its budget, **When** the leg finishes, **Then** reports are uploaded, a P0 escalation runs with a failure conclusion, and the leg fails.
2. **Given** any nightly leg ends cancelled, failed or skipped-by-failure, **When** the summary job runs, **Then** it fails.

---

### User Story 5 - Performance gate measures what it names (Priority: P3)

A maintainer relies on the "100 real closes against a 10k-row spine" performance gate to catch a regression in the close path.

**Why this priority**: The gate currently spends about 95% of its window constructing an executor that is unrelated to the close path. It trips on runner noise and would still miss a genuine per-close regression.

**Independent Test**: The gate passes on a nominal runner and fails if the per-close cost is made proportional to spine size.

**Acceptance Scenarios**:

1. **Given** the close loop is linear in the number of closes, **When** the gate runs, **Then** it passes regardless of one-time setup cost.
2. **Given** a per-close cost proportional to the spine size, **When** the gate runs, **Then** it fails.

### Edge Cases

- A reconciliation-gate test must not be "fixed" by stubbing the gate in a test whose subject is the gate itself. Stubs apply only to tests whose concern lies elsewhere.
- The unmaterialized-coordination dry-run must also handle a coordination branch that was deleted, with the same clean refusal.
- The escalation of an overrun leg must not report success for a partial run.
- A fixture approval that is causally stale must stay ignored by the reducer; only the fixture changes.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Coordination fail-closed re-pin (cause A) | As a maintainer, I want the surface-seam and split-brain tests to assert the fail-closed refusal on an unmaterialized coordination worktree, and the four retention tests to materialize the coordination worktree, so that they pin the ADR 2026-09-24-2 contract. | High | Open |
| FR-002 | Reconciliation stubs for fake-git merge tests (cause B) | As a maintainer, I want the eight merge tests that fake git and the manifest to stub the reconciliation claim and teardown phases, so that they test their own concern. | High | Open |
| FR-003 | Post-fix resume state for resume tests (cause C1) | As a maintainer, I want the merge-resume tests (including the 30s performance budget test) to seed or stub a post-fix resume state, so that they are not refused as pre-fix merges. | High | Open |
| FR-004 | Valid mission identity in planning-lane fixture (cause C2) | As a maintainer, I want the planning-lane fixture to write a lanes manifest that honours the mission-identity invariant, so that the reconciliation claim resolves the real lane branch. | High | Open |
| FR-005 | Approved WP in checkout-safety fixtures (cause C3) | As a maintainer, I want the lane-worktree and primary-checkout safety fixtures to seed WP01 as approved, so that the merge-readiness gate admits them. | High | Open |
| FR-006 | Lanes manifest in arbiter fixture plus guard negative (cause D) | As a maintainer, I want the arbiter-override fixture to write the lanes manifest, and a new test proving the move guard still refuses without it, so that the guard's reach is pinned deliberately. | High | Open |
| FR-007 | Causal rework in retrospect smoke fixture (cause E) | As a maintainer, I want the retrospect smoke fixture to seed the rework transitions between rejection and approval, so that the reduced state is approved. | High | Open |
| FR-008 | Clean merge dry-run refusal on unmaterialized coordination | As an operator, I want `merge --dry-run` to refuse cleanly (message, hint, exit 1, JSON error parity) when the coordination worktree is unmaterialized or the coordination branch is deleted, so that I never see a traceback. | High | Open |
| FR-009 | Fresh merge stop does not wedge the next run | As an operator, I want a fresh merge that stops before consolidation to leave no state that the next plain merge treats as pre-fix, and abort/clear to remove the reconciliation marker, so that I can simply re-run. | Medium | Open |
| FR-010 | Nightly interpreter leg and summary fail closed | As a maintainer, I want an overrunning interpreter leg to still upload, escalate and fail, and the nightly summary to fail on any non-success leg, so that no nightly red is silent. | High | Open |
| FR-011 | Doctor-ops sweep gate measures the close path | As a maintainer, I want the large-spine sweep gate to exclude one-time setup from its measurement and detect per-close regressions, so that it catches real regressions and tolerates runner variance. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Integration lane green | 0 failures in the integration and next test directories attributable to the causes in FR-001..FR-007 when run locally. | Reliability | High | Open |
| NFR-002 | Performance lane green | The two failing performance tests pass locally on 3 consecutive runs. | Performance | High | Open |
| NFR-003 | Quality gates | Lint, format and type checks report 0 issues on changed files; new product code has ≥90% diff coverage. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No green-washing | No test is skipped, xfailed, deleted or retried to reach green; every re-pin cites the product change that moved the contract. | Process | High | Open |
| C-002 | Red-first product fixes | FR-008 and FR-009 each land with a regression test shown failing before the fix, through the pre-existing CLI or executor entry point. | Process | High | Open |
| C-003 | Lane cadence unchanged | The integration test directory stays nightly-only (#5037 ruling); no per-PR routing change. | Technical | Medium | Open |
| C-004 | Deferred follow-ups | The doctrine-graph double-parse optimisation and lane-branch naming unification are out of scope and are filed as follow-up issues. | Business | Medium | Open |
| C-005 | No doctrine pack edits | No changes under `packs/`. | Technical | Medium | Open |

### Key Entities

- **Reconciliation marker**: A per-merge record proving the merge state was created under the terminus reconciliation guarantees. Its absence on a resumed state means "pre-fix".
- **Merge state**: The persisted, resumable progress of a merge.
- **Coordination worktree**: The checkout of a mission's coordination branch that holds lifecycle surfaces; it may be declared but not yet materialized.
- **Nightly leg**: One job of the nightly workflow whose red must escalate to a deduplicated P0 issue.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 25 integration and next tests red in run 36225024230 pass locally, with 0 tests skipped or xfailed to get there.
- **SC-002**: Both performance tests red in run 36225024230 pass locally 3 times in a row.
- **SC-003**: An operator previewing a merge with an unmaterialized coordination worktree sees an actionable message in 100% of attempts and never a traceback.
- **SC-004**: An operator whose fresh merge stopped at a pre-flight gate can re-run a plain merge without manual cleanup.
- **SC-005**: A nightly leg that overruns produces a P0 escalation and a red summary in 100% of cases.

## Assumptions

- The product changes behind causes A–E (#4959, #5001, #4982, #4764, #4758, #4990) are intended and correct. This follows the review squad's analysis and the governing ADRs.
- FR-009 was found by code reading; if it cannot be reproduced, the requirement is recorded as not reproducible and left for follow-up rather than fixed speculatively.
- "Nominal runner" for FR-011 means a GitHub-hosted `ubuntu-latest` 4-vCPU runner.
