# Mission Specification: Owned files unresolved fail closed

**Mission**: `owned-files-unresolved-fail-closed-01M6HAHF`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue #7149, remaining scope after the pre-spec squad (see Background).

## Background

Issue #7149 reported that `spec-kitty accept --owned-checkout` refused every approved work package with
`IMPLEMENTATION_MISSING`, because the evidence gate read each work package's `owned_files` from the
repository root checkout instead of the owned checkout. The pre-spec squad found that this read is
already fixed on `main` by #7099 (commit `088c2f1661`, PR #7103). The report was reproduced on an
older source checkout. A second defect the issue names is still live, and it is the one that led
an operator into rewriting history: whenever the gate cannot read an approved work package's
ownership declaration, it still reports `IMPLEMENTATION_MISSING`. That code tells the operator to
commit more work, or to attest that nothing needed implementing. Neither is true. The real problem
is that the declaration could not be read. This mission makes the gate say so.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An unreadable ownership declaration is named, not mistaken for missing work (Priority: P1)

An operator, or an agent acting for one, runs `spec-kitty accept` (or `consolidate`, or
`orchestrator-api accept-mission`) on a Mission whose approved work package's task file is missing,
or cannot be read. Today the gate answers `IMPLEMENTATION_MISSING` and offers
`--attest-no-implementation`. After this mission it refuses with `OWNERSHIP_UNRESOLVED`, names the
directory or file it tried to read, and tells the operator to restore the task file or to run from
the checkout that owns the Mission.

**Why this priority**: The false code sends operators into history rewrites and false attestations (P0 #7149).

**Independent Test**: An approved work package whose task file is removed from `tasks/` is refused with
`OWNERSHIP_UNRESOLVED`, and the refusal text contains the `tasks/` path. The same fixture, with the
task file present and an owned change in the window, passes the evidence check (positive control).

**Acceptance Scenarios**:

1. **Given** a Mission with an approved work package whose task file is absent from `tasks/`, **When** the operator runs `accept`, **Then** it refuses with `OWNERSHIP_UNRESOLVED` naming that `tasks/` directory, and `IMPLEMENTATION_MISSING` does not appear for that work package.
2. **Given** the same Mission with the `tasks/` directory missing entirely, **When** the operator runs `accept`, **Then** every approved work package is refused with `OWNERSHIP_UNRESOLVED` naming the missing directory.
3. **Given** an approved work package whose task file exists but cannot be parsed, **When** the operator runs `accept`, **Then** it is refused with `OWNERSHIP_UNRESOLVED` naming the directory or file it read.
4. **Given** the task file is present and declares ownership the window changed, **When** the operator runs `accept`, **Then** the evidence check passes (positive control).

---

### User Story 2 - Attestation cannot cover an unreadable declaration (Priority: P1)

An operator facing an `OWNERSHIP_UNRESOLVED` refusal passes `--attest-no-implementation WPnn` to get past it.

**Why this priority**: An attestation says "this work package needed no implementation". It cannot vouch for files the gate never read.

**Independent Test**: The attestation flag on an `OWNERSHIP_UNRESOLVED` work package is refused and records nothing. The same flag on an `IMPLEMENTATION_MISSING` work package (ownership resolved, no owned change) is still accepted (positive control).

**Acceptance Scenarios**:

1. **Given** an approved work package refused with `OWNERSHIP_UNRESOLVED`, **When** the operator runs `accept --attest-no-implementation WPnn --attest-reason "..."`, **Then** the command refuses, names the unresolved read, and records no attestation.
2. **Given** an approved work package with resolved ownership and no owned change, **When** the operator attests it, **Then** the attestation is accepted as today.

---

### User Story 3 - Owned-checkout accept reads canceled work packages from the owned checkout (Priority: P2)

An operator runs `accept --owned-checkout <path>` on a Mission whose status lives only in the owned
checkout, where some work packages were canceled by the operator.

**Why this priority**: The same defect class as #7149: one evidence input (`acceptably_canceled_wp_ids`) still reads the repository root.

**Independent Test**: An owned-checkout Mission absent from the repository root, with one operator-canceled work package, is accepted with that work package excluded, exactly as when the Mission is checked out in the repository root.

**Acceptance Scenarios**:

1. **Given** an owned-checkout Mission absent from the repository root with an operator-canceled work package, **When** the operator runs `accept --owned-checkout`, **Then** the canceled work package is treated as excluded, with the same verdict as the repository-root run of the same Mission.

---

### User Story 4 - Owned move-task says when a work package declares no owned files (Priority: P3)

An agent moves an owned-checkout work package toward review, and the work package declares an empty `owned_files` list.

**Why this priority**: Honesty of the refusal; small and on the same surface.

**Independent Test**: The refusal still uses `OWNED_IMPLEMENTATION_MISSING`, and its message says that the work package declares no `owned_files` and names the task file. A work package with declared files but no matching change keeps the existing message (control).

**Acceptance Scenarios**:

1. **Given** an owned work package whose task file declares `owned_files: []`, **When** it is moved toward review, **Then** the refusal says it declares no owned files and names the task file.

### Edge Cases

- An authored but empty `owned_files` list is a resolved declaration. Today's verdicts are kept: no owned change means `IMPLEMENTATION_MISSING`, and attestation can lift it, because `finalize-tasks` allows an empty list for non-`code_change` work packages.
- A work package that is canceled with operator provenance is excluded before ownership is read, so it is never reported unresolved.
- A single_branch Mission reports the same unresolved condition under its own code family if the alias map requires one, and never as `SINGLE_BRANCH_IMPLEMENTATION_MISSING`.
- Several approved work packages each get their own line, so a Mission where some resolve and some do not reports each one correctly.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Unresolved ownership has its own verdict | As an operator, I want an approved work package whose task file is absent, unreadable, or whose `tasks/` directory is missing to be refused with `OWNERSHIP_UNRESOLVED`, so that I am not told to implement work that may already exist. | High | Open | build | no |
| FR-002 | The refusal names what was read | As an operator, I want the `OWNERSHIP_UNRESOLVED` line to name the directory or file the gate tried to read, and its recovery to say how to restore the read (restore the task file, or run from the checkout that owns the Mission), so that I can fix the right thing. | High | Open | build | no |
| FR-003 | Unresolved is checked before missing | As an operator, I want `IMPLEMENTATION_MISSING` reported only when ownership was resolved and the window holds no owned change, so that the two causes never share a code. | High | Open | build | no |
| FR-004 | Attestation cannot lift it | As a maintainer, I want `--attest-no-implementation` refused for a work package whose ownership is unresolved, with nothing recorded, so that no attestation stands in for an unread declaration. | High | Open | build | no |
| FR-005 | Every evidence consumer reports the new code | As an orchestrator integrator, I want `accept`, `consolidate` and `orchestrator-api` to surface `OWNERSHIP_UNRESOLVED` through the same predicate, and the code to be listed in the documented code registry, so that automation can branch on it. | Medium | Open | build | no |
| FR-006 | Owned accept reads canceled work packages from the owned checkout | As an operator running `accept --owned-checkout`, I want the canceled-work-package set read from the owned checkout, so that a Mission absent from the repository root is judged as if it were checked out there. | Medium | Open | build | no |
| FR-007 | Owned move-task names an empty declaration | As an agent, I want the owned review-ward `move-task` refusal for a work package declaring no `owned_files` to say so and name the task file, keeping the code `OWNED_IMPLEMENTATION_MISSING`, so that the refusal is not mistaken for missing commits. | Low | Open | build | no |
| FR-008 | Resolved ownership keeps today's verdicts | As an operator, I want every work package whose ownership resolves, including an authored empty list, to get exactly today's verdicts, so that the change narrows only the unresolved case. | High | Open | ratchet | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added git work | The verdict adds no git subprocess call per work package; the unresolved check uses the task-file read the gate already performs. | Performance | Medium | Open |
| NFR-002 | Red-first coverage | Each of FR-001, FR-004, FR-006 and FR-007 has a regression test that fails on the pre-mission code and passes after, through the production entry point (the CLI command or `mission_evidence_report`), each paired with a same-fixture positive control. | Reliability | High | Open |
| NFR-003 | Clean gates | The changed modules pass `ruff` and `mypy` with zero new findings; no new suppression is added. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One predicate | The verdict is decided once, in the shared evidence predicate (`wp_evidence`); callers never re-derive it. | Technical | High | Open |
| C-002 | No change to the owned read | The owned-checkout read fixed by #7099 is not re-implemented; the existing `placement_seam(..., owned=...)` route is reused. | Technical | High | Open |
| C-003 | Out of scope | #7081 (tracer append, PR #7129), #5458 (owned move-task gate skip; collides with PR #7146), `agent tasks add-history --owned-checkout`, and owned-checkout support for `consolidate` / `orchestrator-api` are not changed. | Business | High | Open |
| C-004 | Evidence windows unchanged | How evidence windows are computed is not changed (open work on that surface: #7120 / PR #7146). | Technical | Medium | Open |

### Key Entities

- **Ownership declaration**: the `owned_files` list authored in a work package's task file under the Mission's `tasks/` directory.
- **Evidence verdict code**: a stable refusal code produced by the evidence predicate (`IMPLEMENTATION_MISSING`, `IMPLEMENTATION_UNREADABLE`, `REVIEW_NOT_INDEPENDENT`, `EVIDENCE_WINDOW_UNCOMPUTABLE`, and now `OWNERSHIP_UNRESOLVED`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of fixtures where an approved work package's task file or `tasks/` directory is missing or unreadable, `accept` reports `OWNERSHIP_UNRESOLVED` and never `IMPLEMENTATION_MISSING` for that work package. — [build] · no-op passable: no
- **SC-002**: 0 attestations are recorded for an unresolved work package across the attestation tests. — [build] · no-op passable: no
- **SC-003**: An owned-checkout Mission absent from the repository root receives the same accept verdict as the same Mission checked out in the repository root, in every fixture. — [build] · no-op passable: no
- **SC-004**: Every existing evidence test for resolved ownership passes unchanged (0 regressions in the evidence test modules). — [ratchet] · no-op passable: yes (positive control: SC-001's red-first tests fail on the pre-mission code)

## Assumptions

- The pre-spec squad's reproduction stands: the owned read is fixed on `main` (`tests/integration/test_owned_acceptance_authority_6023.py` passes on `main` and fails on `01dbf46158`).
- The orchestrator-api error contract takes the new code as a backward-compatible addition: `CONTRACT_VERSION` 1.22.0 -> 1.23.0, following the 1.21.0 precedent.
