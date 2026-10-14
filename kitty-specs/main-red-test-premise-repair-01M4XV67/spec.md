# Mission Specification: Restore green main: stale test premises after the requirement-grammar scoping and the events 10.4.6 bump

**Mission Branch**: `issue-6240-main-red-test-premise-repair`  
**Created**: 2026-10-14  
**Status**: Draft  
**Input**: Issues #6240 and #6238 (folded together by operator steer), plus an operator scope ruling on dependency-bump shard selection.

## Intent Summary (confirmed)

- **Primary actor**: a Spec Kitty maintainer or contributor whose PR, or the nightly run, depends on an honest test signal from `main`.
- **Trigger**: the nightly run and every PR that selects the `upgrade` module shards go red on two tests whose premises lagged shipped changes. Neither failure is a product defect.
- **Desired outcome**: both tests pass on `main` against the shipped contract, the audit they exercise stays as strict as it is today, and a future reducer-dependency bump that lands through the lock file runs the shards that would have caught this.
- **Invariant**: no test, audit or classifier is loosened to reach green. Corrections reach the fixture only through the existing operator-sanctioned corrections list.
- **Boundary**: an edit to the project manifest alone (for example a rename or a non-version edit) must not trigger the upgrade shards. Only the lock file does.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The requirement-ID lint test matches the shipped grammar (Priority: P1)

A maintainer runs the requirement-ID lint tests. They pass, and they cover the behaviour the grammar now has: requirement kinds are scoped by Mission type, and template placeholders are rejected.

**Why this priority**: it reds the nightly on two jobs today (#6240).

**Independent Test**: run the lint test file in isolation. All cases pass, and a case for each Mission-type branch exists.

**Acceptance Scenarios**:

1. **Given** the five existing well-formedness cases, **When** they are checked under the software-dev Mission type, **Then** each gives its existing expected verdict.
2. **Given** a research-only requirement kind (for example `DR-001`), **When** it is checked under the research Mission type, **Then** it is well-formed; **and when** it is checked under software-dev, **Then** it is not.
3. **Given** a template placeholder in a declared position (for example `FR-00N`), **When** it is checked under either Mission type, **Then** it is not well-formed.

### User Story 2 - The full-corpus recovery audit passes on the pinned historical corpus (Priority: P1)

A maintainer runs the full-corpus recovery audit tests. The healthy baseline audit reports no teamspace blocker, because the fixture carries the same operator-sanctioned correction the live corpus already carries.

**Why this priority**: it reds `main` for every PR that selects the upgrade shards, and fail-fast then cancels most other module shards (#6238).

**Independent Test**: run the full-corpus recovery test in isolation under the pinned reducer version. All three variants pass.

**Acceptance Scenarios**:

1. **Given** the full historical corpus exported from its pinned commit, **When** the fixture is built, **Then** every path in the operator-sanctioned corrections list that exists in the export carries its sanctioned bytes, applied as a separate, labelled fixture commit.
2. **Given** that fixture, **When** the strict mission-state audit runs, **Then** it reports zero teamspace blockers. The scanner-membership fault variants still reject their injected faults.
3. **Given** a sanctioned path that does not exist in the historical export, **When** the fixture is built, **Then** it is skipped, not created.

### User Story 3 - A lock-file reducer bump runs the shards that reduce status events (Priority: P2)

A maintainer opens a PR that changes the lock file (for example, a reducer-package bump). CI selects the upgrade and status module shards for that PR. A PR that changes only the project manifest does not select the upgrade shards through this route.

**Why this priority**: it closes the gap that let #6238 merge unseen. It is secondary to restoring green.

**Independent Test**: call the shard-selection authority with a changed-path set containing only the lock file, then with only the project manifest, and compare the selected modules.

**Acceptance Scenarios**:

1. **Given** a diff that touches only `uv.lock`, **When** the module selection is computed, **Then** it includes `upgrade` and `status`.
2. **Given** a diff that touches only `pyproject.toml`, **When** the module selection is computed, **Then** this mission's routing does not add `upgrade`.

### Edge Cases

- A sanctioned correction path that is absent from the pinned export is skipped.
- A sanctioned correction whose current bytes would make another fixture-based assertion fail is surfaced, not silently applied. The overlay is limited to paths present in the export, and the existing recovery and byte-identity tests are run to confirm.
- The routing change must keep the group non-src, so it never masks an unmapped `src/**` change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Lint test re-pinned to the Mission-type-aware signature | As a maintainer, I want the well-formedness test to call the helper with an explicit Mission type so that it exercises the shipped contract (#6240). | High | Open | [ratchet] | no — the test is red at the base commit and must be green after |
| FR-002 | Research-scoped kinds and placeholder rejection covered | As a maintainer, I want cases proving a research-only kind is valid only under research, and a placeholder is never well-formed, so that the c0f455d06 behaviour is pinned (#6240). | High | Open | [ratchet] | no — paired positive/negative verdicts on the same token |
| FR-003 | Full-corpus fixture carries the sanctioned corrections | As a maintainer, I want the full-corpus recovery fixture to apply the operator-sanctioned corrections, read from the single existing list, so that the strict audit agrees with the live corpus (#6238). | High | Open | [ratchet] | no — the audit exits 1 at the base commit and 0 after |
| FR-004 | Lock-file change selects the upgrade and status shards | As a maintainer, I want a `uv.lock` change to select the upgrade and status module shards, and a `pyproject.toml`-only change not to select upgrade through this route, so that a lock-file reducer bump is tested before merge (#6238). | Medium | Open | [build] | no — paired lock-only vs manifest-only selection |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Audit strictness preserved | Zero new classifier tolerances, allowlist entries or skipped assertions in the audit and recovery tests. The count of `_OPERATOR_SANCTIONED_CORRECTIONS` entries is unchanged. | Reliability | High | Open |
| NFR-002 | Bounded CI cost | The routing change adds shard selection for exactly one path (`uv.lock`) and at most two modules (`upgrade`, `status`). | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No product code change | Changes are confined to tests, test fixtures and CI routing configuration. No `src/` behaviour changes. | Technical | High | Open |
| C-002 | Single authority for sanctioned corrections | The fixture reads the existing sanctioned-corrections list. It must not keep its own copy of the paths. | Technical | High | Open |
| C-003 | Project manifest excluded from the new route | `pyproject.toml` is not added to the new fan-out group (operator ruling, decision 01M4XV6HM7WHEB2B8QG67N29HT). | Business | High | Open |

### Key Entities

- **Operator-sanctioned corrections list**: the reviewed set of corpus files whose bytes an operator deliberately changed after the byte-freeze. It is the only authority for which historical bytes may differ.
- **Full-corpus recovery fixture**: a throwaway repository built from a pinned historical commit, used to prove the recovery path and the strict audit.
- **Module fan-out group**: a non-src path group that adds named module shards to CI selection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The requirement-ID lint test file passes in full (0 failures, up from 5), under both the software-dev and research Mission types — [ratchet] · no-op passable: no
- **SC-002**: All 3 variants of the full-corpus recovery audit test pass under the pinned reducer version (0 failures, up from 3) — [ratchet] · no-op passable: no
- **SC-003**: The nightly jobs that failed on these tests ("specify_cli out-of-matrix trees", "Interpreter matrix shard 5") pass on their next run after merge — [ratchet] · no-op passable: no
- **SC-004**: A lock-file-only change selects 2 additional module shards (`upgrade`, `status`); a manifest-only change selects 0 additional upgrade shards through the new route — [build] · no-op passable: no

## Out of Scope (follow-ups, named in the PR)

- The shared subprocess test virtualenv (`tests/conftest.py`) installs the newest allowed reducer package rather than the locked one, so subprocess CLI tests can run a reducer version other than the pin.
- A broader per-PR lane for the specify_cli out-of-matrix tree. Follow-up: #4732.
