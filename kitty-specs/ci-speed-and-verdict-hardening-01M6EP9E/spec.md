# Mission Specification: CI speed and verdict hardening

**Mission Branch**: `ci/speed-and-verdict-hardening`

**Created**: 2026-11-02

**Status**: Implementation submitted for PR review; not accepted or merged

**Input**: The operator approved the preceding in-depth CI review and requested a high-quality complete implementation, using DeepSeek V4.1 Flash 1017 for any subagents, delivered as a PR without merging.

## Intent Summary

For Spec Kitty maintainers and contributors, reduce repeated CI computation and obsolete work while preserving genuine verification. A normal pull request must still receive stable, truthful checks. A failed full-mode shard or coverage from another revision must never become a green result. Implement concrete fixes from the approved review; benchmark-dependent capacity changes are experiments, not permission to weaken checks. The local Mission targets the topic branch; publication is a draft PR targeting `main`, merged only by the operator.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trust the result (Priority: P1)

A maintainer checks a full test run and a coverage report before deciding whether a revision is ready.

**Independent Test**: Execute the shipped shard shell with controlled pytest exit codes; exercise coverage selection with same-revision and mismatched API responses.

**Acceptance Scenarios**:

1. **Given** a failing pytest shard in either execution mode, **When** the run ends, **Then** the job reports that failure and still attempts report upload.
2. **Given** coverage for another revision, **When** the nightly report selects artifacts, **Then** it refuses that coverage rather than attributing it to the current source.
3. **Given** a complete same-revision report, **When** it is selected, **Then** it remains usable and informational reporting remains outside the merge gate.

### User Story 2 - Avoid repeated work (Priority: P1)

A contributor submits a change and receives the same checks without duplicate source scans, lint environments, checkout, or unnecessary repository setup.

**Independent Test**: Count scanner invocations, mutate scratch trees, inspect the workflow graph and test pure versus repository-dependent fixture consumers.

**Acceptance Scenarios**:

1. **Given** multiple assertions over an unchanged source tree, **When** they run, **Then** source facts are computed once without dropping assertions.
2. **Given** a scratch tree changed between probes, **When** the guard runs again, **Then** it observes the changed violation.
3. **Given** an unrelated temporary-directory isolation fixture, **When** a pure charter test runs, **Then** that fixture alone does not require git initialization.

### User Story 3 - Reuse valid inputs, not stale assumptions (Priority: P2)

A contributor adds or reorders tests, updates dependencies, or pushes a new revision while earlier checks run.

**Independent Test**: Exercise identity-keyed weighting, malformed capture rejection, cache identity changes, packaging-input classification and supersession groups.

**Acceptance Scenarios**:

1. **Given** reordered or newly added tests, **When** shards are selected, **Then** unchanged test identities retain their measured weights and new identities receive an explicit deterministic fallback.
2. **Given** changed pins, environment mode or asset class, **When** cache inputs are computed, **Then** incompatible cached material cannot satisfy the request.
3. **Given** only proven package-irrelevant prose changes, **When** packaging is evaluated, **Then** the stable required check succeeds without a redundant wheel build; uncertain inputs still build and clean-install.
4. **Given** a superseding PR push, **When** Windows runs are grouped, **Then** obsolete work can be cancelled without cancelling independent mainline evidence.

### Edge Cases

Missing diff bases, failed API queries, malformed/partial timings, identical-count test replacement, unavailable exact-revision coverage, dangling interpreter links, cold concurrent caches, fork PRs, pause-label events, historical git consumers, scratch mutations, future packaging inputs and non-gating WIP scenarios.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Truthful full-mode verdict | Failed module tests remain failed in both modes, without disabling report upload or full-mode run-all behavior. | High | Open | [build] | no |
| FR-002 | Revision-bound coverage | Nightly reporting accepts only successful module evidence for the checked-out revision. | High | Open | [build] | no |
| FR-003 | Shared immutable scan facts | Repeated repository assertions reuse source facts while mutation probes remain fresh. | High | Open | [build] | no |
| FR-004 | Single lint owner | Each normal event has one Ruff/lock execution owner and preserves stable required gate coverage. | High | Open | [build] | no |
| FR-005 | Single shard checkout | Test environment warmup consumes the caller's checkout instead of repeating it. | Medium | Open | [build] | no |
| FR-006 | Honest environment reuse | Dependency identity comes from actual locked/resolved inputs, and restored environments are usable or rebuilt honestly. | High | Open | [build] | no |
| FR-007 | Cache asset isolation | Pack data is restored before build hooks need it; service extras/full requests use distinct compatible cache identities. | Medium | Open | [build] | no |
| FR-008 | Identity-based weights | Fresh captures retain test identities; reorder/add/remove does not silently misassociate or discard unaffected measurements. | High | Open | [build] | no |
| FR-009 | Targeted repository fixtures | Pure charter tests do not initialize git solely through an unrelated autouse temporary-directory dependency. | Medium | Open | [build] | no |
| FR-010 | Obsolete run cancellation | Superseded Windows PR checks cancel within an isolated concurrency group. | Medium | Open | [build] | no |
| FR-011 | Observable phases | Collection-policy cache/scan and workflow install/test phases are separately observable without weakening the policy guard. | Medium | Open | [build] | no |
| FR-012 | Conservative package scoping | Only demonstrably irrelevant prose changes omit wheel work; required checks still report and uncertainty builds. | Medium | Open | [build] | no |
| FR-013 | Cached pinned tooling | Site/JVM/docs tooling reuses dependency material with pinned versions/checksums and never cached acceptance verdicts. | Medium | Open | [build] | no |
| FR-014 | Complete operator handoff | A reviewed draft PR records validation, remaining evidence limitations and any policy-sensitive experiments; no merge occurs. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behavioral fidelity | Zero intentionally dropped selected tests, cross-package coverage targets or scratch mutation controls. | Reliability | High | Open |
| NFR-002 | Focused validation | Every added/modified behavior has a focused regression test; new testable code targets at least 90% coverage. | Quality | High | Open |
| NFR-003 | Honest performance evidence | Zero claimed measured speedups without a before/after measurement; distinguish computation from scheduling gaps. | Observability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Publication boundary | Open a PR to main; do not merge or push main. | Governance | High | Open |
| C-002 | Model choice | All subagents use DeepSeek V4.1 Flash 1017. | Operational | High | Open |
| C-003 | Fail closed | Preserve source identity, fork/secret safety, pause-label semantics, required checks and historical git objects. | Security | High | Open |
| C-004 | Test isolation | Do not share mutable repositories or blindly enable intra-shard xdist. | Reliability | High | Open |
| C-005 | Evidence before capacity | Do not increase fan-out, add debounce, disable lanes or delete caches without evidence supporting that specific change. | Performance | Medium | Open |

### Key Entities

- **Revision evidence**: reports and captured measurements tied to the source they describe.
- **Test identity**: collected node identity used to associate a test with its measured duration.
- **Execution mode**: PR versus full behavior, differing in cancellation/diagnostics but not truthfulness.
- **Cache identity**: content, runtime and requested asset-class boundary governing safe reuse.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A failing shard cannot pass in either mode, and reports are still attempted. — [build] · no-op passable: no
- **SC-002**: Same-count replacement and reordering cannot transfer a duration to another test identity. — [build] · no-op passable: no
- **SC-003**: The selected duplicate computation/environment jobs are removed with all corresponding independent assertions retained. — [build] · no-op passable: no
- **SC-004**: The operator receives an unmerged draft PR with reproducible focused test results and limitations. — [build] · no-op passable: no
