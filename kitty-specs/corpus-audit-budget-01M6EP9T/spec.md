# Mission Specification: Calibrate the full-corpus recovery test budget

**Mission Branch**: `issue-5716-corpus-audit-budget`  
**Created**: 2026-11-02  
**Status**: Draft  
**Input**: The operator authorized separate work on #5716 if needed to unblock reviewed PR #7071. Measure first; preserve the corpus recovery contract and required CI checks.

## User Scenarios & Testing

### User Story 1 - Measure the real CI workload (Priority: P1)

As a maintainer, I need a complete measurement of the existing full-corpus recovery test on the hosted CI runner so its execution limit is based on evidence rather than repeated kills at the shared 240-second hang backstop.

**Why this priority**: The same timeout blocks unrelated upgrade PRs, including #7071, and occurs on unmodified main. A local diagnostic stalled on a different inner subprocess boundary, so it cannot establish the hosted runner's required total.

**Independent Test**: Run this single existing test once with a bounded diagnostic outer limit on the normal CI runner, record total and per-audit elapsed times, and retain its original assertions and inner subprocess limit.

**Acceptance Scenarios**:

1. **Given** current main and the pinned historical corpus, **when** the exact failing test is measured on a hosted runner, **then** the evidence identifies source SHA, runner, elapsed total, each audit duration, exit status and any timeout without retries.
2. **Given** the diagnostic run times out or fails a real assertion, **when** its evidence is assessed, **then** that outcome is reported honestly and no successful calibration is claimed.

### User Story 2 - Restore a useful, bounded correctness guard (Priority: P2)

As a maintainer, I need the recovery contract to complete within an evidence-calibrated test-local budget while still catching corrupted historical artifacts, so unrelated PRs can use the upgrade shard as a meaningful gate.

**Independent Test**: Run the unchanged behavioral contract under the proposed final limit; check all original memberships, inventories, recovery gates and attack/control pairs remain.

**Acceptance Scenarios**:

1. **Given** a successful diagnostic measurement, **when** an independent reviewer approves the remedy, **then** a narrowly scoped change applies only the justified budget or demonstrated bottleneck correction and the full contract passes.
2. **Given** a corrupted corpus artifact, **when** the existing attack loop audits it, **then** it still detects the blocker and a restored healthy control still passes.

### Edge Cases

- An individual audit exceeds its existing 180-second subprocess limit: preserve and report that evidence rather than increasing it without measurement.
- The hosted runner cannot finish within the diagnostic upper bound: stop budget calibration and investigate the bottleneck; do not introduce an unbounded run.
- Main advances: preserve the distinction between the measured source and the final reviewed source, rerunning only the affected test if the relevant code changed.
- The diagnostic job fails setup or cannot fetch pinned historical Git objects: classify setup failure, not corpus execution time.

## Requirements

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Hosted measurement | As a maintainer, I want a bounded hosted-runner measurement of the exact failing test and its audit phases so that the budget has a reproducible basis. | High | Open | [build] | no |
| FR-002 | Evidence-calibrated correction | As a maintainer, I want the smallest justified correction to the test's execution budget or proven bottleneck so that the existing corpus contract completes reliably. | High | Open | [build] | no |
| FR-003 | Preserve integrity controls | As a maintainer, I want all eleven full-corpus audits, membership comparisons, inventories, recovery gates and healthy controls preserved so that timing remediation does not hide a defect. | High | Open | [ratchet] | yes — paired with the actual calibrated correction and existing corruption controls |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded diagnostics | Diagnostic execution runs only the named test, with an outer limit no greater than 900 seconds and a job limit no greater than 25 minutes. | Reliability | High | Open |
| NFR-002 | Quantified headroom | A final test-local timeout, if chosen, must be justified from measured hosted total plus explicit headroom; do not tune the inner 180-second subprocess limit without separate evidence. | Reliability | High | Open |
| NFR-003 | No repeated measurement to green | Every attempted measurement is retained with source and outcome; no retry plugin or retry-to-green is introduced. | Integrity | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Separate scope | Keep #7071's reviewed fixture change untouched. No global pytest timeout increase, skip, xfail, quarantine, weakened assertion or silent move to nightly. | Technical | High | Open |
| C-002 | Minimal permanent surface | Diagnostic instrumentation may be temporary; retain only useful evidence and the independently reviewed final correction. No new config-value or code-shape test. | Maintenance | High | Open |
| C-003 | Existing workflow | Use canonical Mission commands, isolated branch, independent reviews, draft PR, targeted validation and required CI gates. Never push main or bypass merge controls. | Governance | High | Open |

### Key Entities

- **Measured run**: source commit, runner identity, total duration, per-audit durations, unchanged inner limit, outcome and artifact URL.
- **Budget decision**: the evidence-backed final execution limit or proven bottleneck correction and its preserved invariants.

## Success Criteria

- **SC-001**: At least one bounded hosted-runner measurement records all completed audit phases and the final outcome for the exact failing test. — [build] · no-op passable: no
- **SC-002**: The complete existing recovery contract passes with the final evidence-backed correction and no dropped integrity controls. — [build] · no-op passable: no
- **SC-003**: Two independently dispatched reviewers with distinct profile identities, neither the implementer, assess evidence/correctness and final test integrity; the ready PR records their findings, CI results and any remaining blockers for #7071. — [ratchet] · no-op passable: no

## Grounding and Scope

Issue #5716 is open and assigned to Ivan-Melck. The current failing node is `tests/upgrade/test_mission_corpus_recovery.py::test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes`. Current-main evidence and PR #7071 both show the shared 240-second pytest timeout during a healthy control, not a failed recovery assertion. Its historical corpus has 423 directories and about 228 MB of data. The test launches eleven sequential real CLI audits plus inventories and recovery gates. The prior independent adjudication found no safe small fix without hosted measurement. The local extended diagnostic instead hit an individual audit's 180-second subprocess timeout, whose cause is undetermined; it is not a CI budget measurement.

Out of scope: production audit semantics, migration behavior, the unrelated maintenance fix in #7071, suite-wide scheduling policy and release/merge controls. If measurements demonstrate a production bottleneck requiring a broader change, record the finding and seek scope approval rather than silently expanding this Mission.
