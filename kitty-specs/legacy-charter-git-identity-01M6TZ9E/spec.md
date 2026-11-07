# Mission Specification: Hermetic legacy-charter Git identity fixtures

**Mission Branch**: `issue-7061-legacy-charter-git-identity`
**Created**: 2026-11-07
**Status**: Draft
**Input**: Issue #7061 and the operator's focused remediation instruction

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run owned-checkout migration tests without ambient Git identity (Priority: P1)

A maintainer or isolated CI worker runs the legacy-charter migration tests and reaches the intended owned-checkout assertions without depending on machine-global Git configuration.

**Why this priority**: The three remaining failures keep the Python 3.13 nightly shard honestly red and prevent the tests from exercising their actual migration and cache-expiry contracts.

**Independent Test**: Run the three reported pytest nodes with no source changes to reproduce `Author identity unknown`; after the fixture-only patch, run the same nodes and their four-case behavior matrix.

**Acceptance Scenarios**:

1. **Given** either affected repository setup, **When** its bootstrap commit finishes, **Then** repository-local `user.name=t` and `user.email=t@t` remain available to subsequent commits in the linked owned worktree.
2. **Given** the three reported nodes, **When** they run after the patch, **Then** all three pass through their unchanged production-path assertions.
3. **Given** `test_cli_startup_claim_is_not_reused_by_later_commands[True]`, **When** the four-case matrix runs, **Then** it still passes for the intended early out-of-range-schema refusal.

### Edge Cases

- The linked owned worktree must inherit identity from the initialized repository without global configuration.
- The intentional `[True]` early-failure sibling must not turn into a successful Mission creation.
- Existing legacy-primary refusals, placement assertions, and cache-expiry assertions must remain unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Persist fixture-local Git identity | As a test maintainer, I want both affected setups to configure repository-local identity immediately after `git init` so later `safe_commit` calls do not depend on ambient configuration. | High | Open | [build] | no — the same three CLI-level nodes fail before the edit |
| FR-002 | Preserve tested production behavior | As a maintainer, I want the patch confined to fixture setup so all existing migration, refusal, and cache-expiry assertions continue to judge the unchanged production path. | High | Open | [ratchet] | yes — paired with FR-001's pre-patch red and post-patch green controls on the same nodes |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Hermetic test setup | The two setups add exactly four repository-local Git configuration commands and require zero global Git identity mutations. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Narrow #7061 scope | Change only `tests/specify_cli/migration/test_legacy_charter_gate.py`, Mission governance artifacts, and the required changelog fragment; do not change `safe_commit`, CI identity, or test assertions. | Technical | High | Open |
| C-002 | Excluded work | Do not address #7206, #6788, startup performance, or unrelated recovered nightly failures, and do not repurpose PR #7273 or #7287. | Business | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The three exact issue-reported nodes move from **3 failed** before the edit to **3 passed** after it. — [build] · no-op passable: no
- **SC-002**: The two affected test functions' complete matrix reports **4 passed**, including the intentional `[True]` early-refusal sibling. — [ratchet] · no-op passable: no — three matrix cases are red before the edit
- **SC-003**: The owning test file and targeted Ruff lint/format checks pass with no production-source diff. — [ratchet] · no-op passable: no — the owning file has three failures before the edit
- **SC-004**: Closure of #7061 is claimed only after the relevant Python 3.13 nightly shard 5 runs green on the merged commit; local green alone is hand-off evidence. — [ratchet] · no-op passable: yes — this is an explicit verification boundary, not an implementation result
