# Mission Specification: Safe analysis report transactions

**Mission Branch**: `fix/analysis-report-transaction`  
**Created**: 2026-09-24  
**Status**: Specified  
**Input**: Approved replay workflow repair and analysis-recorder-safe-transaction-design.md architecture intake. Audience: software engineers operating governed missions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve unrelated work (Priority: P1)

An operator records analysis while unrelated application changes remain in the authoritative planning checkout. Explicit report-only mode commits only the report and preserves unrelated working and staged content, including partial staging.

**Why this priority**: Stashing shared changes interrupts other owners and can lose staging intent.

**Independent Test**: A real repository with clean mission inputs and a partially staged unrelated file produces a report-only commit; staged blob, working bytes, and untracked bytes remain unchanged.

**Acceptance Scenarios**:

1. **Given** unrelated changes and explicit report-only mode, **when** recording succeeds, **then** only the report is committed on the declared unprotected planning branch.
2. **Given** the same changes without opt-in, **when** recording runs, **then** the existing broad dirty-tree guard refuses before report mutation.

### User Story 2 - Refuse unsafe evidence (Priority: P1)

An operator must not receive apparently current analysis based on uncommitted or concurrently changing material inputs.

**Why this priority**: A clean lane does not establish clean authoritative governance.

**Independent Test**: Dirty or concurrently changed material inputs refuse the transaction; later material changes make recorded analysis stale.

**Acceptance Scenarios**:

1. **Given** dirty authoritative charter, selected mission configuration, spec, plan, tasks, WP definition, metadata, or report, **when** opt-in recording runs, **then** it refuses before mutation.
2. **Given** detached, protected, wrong, or concurrently moved target branch, **when** recording runs, **then** no successful transaction is reported.
3. **Given** linked-checkout invocation, **when** placement resolves, **then** the existing authoritative primary partition remains the report destination.

### User Story 3 - Recover from failed recording (Priority: P2)

An operator can distinguish a committed report from a disk write or failed commit.

**Why this priority**: Success must represent the actual committed outcome.

**Independent Test**: Inject render, write, staging, and commit failures and assert non-success with truthful recovery status and no unrelated content capture.

### Edge Cases

Rename endpoints, unusual filenames, symlink escapes, conflicted indexes, active Git operations, concurrent input/index/HEAD movement, hook rejection, and unchanged reports have deterministic outcomes. Unsupported states fail closed.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Explicit transaction | Opt into report-only behavior; default broad guard remains. | High | Open |
| FR-002 | Preserve unrelated state | Only report commits; unrelated staged blobs, flags, working and untracked bytes survive. No stash. | High | Open |
| FR-003 | Material input guard | Dirty report, mission planning definitions, and resolved governance inputs refuse before mutation. | High | Open |
| FR-004 | Branch and race guard | Canonical protection applies; observed concurrent HEAD, index, or input changes abort or produce explicit recovery failure. | High | Open |
| FR-005 | Honest outcome | Distinguish committed, unchanged, failed-before-write, and written-but-uncommitted; never suppress failure. | High | Open |
| FR-006 | Freshness | Shared material manifest determines preflight and freshness; material changes invalidate reports without incidental status churn. | High | Open |
| FR-007 | Placement | Linked invocation retains canonical primary report placement and planning target. | High | Open |

### Non-Functional Requirements

| ID | Requirement | Measure | Status |
|----|-------------|---------|--------|
| NFR-001 | Preservation proof | Real-Git tests verify exact unrelated staged blob and working/untracked bytes across success and failures. | Open |
| NFR-002 | Failure proof | Every refusal returns nonzero without false success; successful changed-path set contains only report. | Open |
| NFR-003 | Focused qualification | New code reaches 90% coverage with recorder, freshness, and commit tests plus required fast baseline. | Open |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | Extend canonical placement, commit, and freshness authorities; no parallel authorization or bypass. | Open |
| C-002 | No Aletheia or PR5009 edits, global runtime install, or new checkout. | Open |
| C-003 | Preserve default behavior; refuse unsupported concurrency/index states instead of claiming safe preservation. | Open |

## Key Entities

Report transaction; authoritative planning checkout; declared commit target; material input manifest; unrelated operator work; explicit recovery outcome.

## Assumptions

User authorization covers this bounded supported repair and ordinary engineering decisions. Current source already prefers authoritative charter YAML and path-scoped commits without stash; reuse these. External governance dependencies must be resolved explicitly.

## Success Criteria *(mandatory)*

- All seven functional requirements have passing acceptance tests.
- Default invocation stays conservative; opt-in succeeds with unrelated partial staging and preserves exact content.
- Dirty material inputs still block replay until their owner reconciles them.
- Independent review clears correctness; validated source is published separately from PR5009.
