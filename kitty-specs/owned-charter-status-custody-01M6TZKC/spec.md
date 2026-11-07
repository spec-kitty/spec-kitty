# Mission Specification: Owned Mission coordination status charter custody

**Mission Branch**: `issue-6788-owned-charter-status-custody`  
**Created**: 2026-11-07  
**Status**: Draft  
**Input**: #6788 owned-Mission custody slice

## Intent Summary

An operator advancing a validated owned `lanes_with_coord` Mission must be able to build the step prompt when the runtime supplies that Mission's canonical coordination status directory. Only the owned primary Mission directory and this same Mission's canonical status directory are admissible; every foreign directory must remain refused. Governance stays anchored to the validated owned primary Mission directory. The binding task brief completed minimal discovery by supplying the actor, trigger, outcome, custody invariant, exclusions, and acceptance entry points.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Advance from canonical coordination status (Priority: P1)

An operator advances an owned Mission whose status is materialized on its coordination surface. The runtime presents that canonical status directory while constructing the next step prompt.

**Why this priority**: Twenty installed-CLI nightly reproductions currently stop valid owned Mission advances with `MISSION_CONTEXT_CONFLICT`.

**Independent Test**: Build a prompt through the real owned prompt path with a valid owned `lanes_with_coord` Mission and its materialized canonical status directory; then run the existing installed-CLI concurrency parameter `[0]`.

**Acceptance Scenarios**:

1. **Given** a validated owned Mission and a materialized canonical status directory distinct from its primary Mission directory, **When** the advancing step builds its prompt, **Then** prompt production succeeds without changing the owned charter anchor or the primary snapshot.
2. **Given** that same owned Mission, **When** the runtime supplies its primary Mission directory, **Then** the existing same-path behavior still succeeds without an additional placement lookup.
3. **Given** that same owned Mission, **When** any unequal foreign directory or another Mission's status directory is supplied, **Then** prompt production still fails closed with `MISSION_CONTEXT_CONFLICT`.

### Edge Cases

- An unmaterialized coordination surface must be tolerated by canonical resolution; it must not turn into permission to accept an arbitrary path.
- Path comparison occurs after path resolution so aliases of one canonical directory do not create a false custody conflict.
- A failed or ambiguous canonical Mission resolution must not silently admit the supplied directory.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Admit same-Mission canonical status | As an operator, I want an owned Mission's canonical coordination status directory accepted for prompt governance so that valid advances are not blocked. | High | Open | [build] | no |
| FR-002 | Preserve primary fast path | As an operator, I want the owned primary Mission directory to retain its direct admission path so existing behavior gains no placement-resolution work. | High | Open | [ratchet] | yes — the FR-001 unequal-path positive control proves the resolver is exercised only where needed |
| FR-003 | Preserve foreign-path refusal | As an operator, I want every directory other than the two canonical same-Mission surfaces refused so custody cannot cross Mission boundaries. | High | Open | [ratchet] | yes — the FR-001 same-fixture success is the positive control for the refusal probe |
| FR-004 | Preserve owned charter anchor | As an operator, I want governance resolved from the validated owned root and primary Mission directory even when the runtime presents the coordination status directory. | High | Open | [ratchet] | yes — the FR-001 prompt must expose the owned marker while the primary snapshot remains unchanged |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded verification | The focused owned prompt and owned runtime integration files plus installed-CLI parameter `[0]` must pass; all 20 installed-CLI parameters must be left for the owning nightly rather than a local full-matrix run. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Canonical placement only | On only the unequal-path arm, canonical status identity must come from `mission_context_for(owned.repository_root, owned.mission_slug, owned=owned, tolerate_unmaterialized_coord=True)` and exact `STATUS_STATE.read_dir` equality. | Technical | High | Open |
| C-002 | Minimal custody change | Keep the same-path fast path, foreign-directory refusal, and `CharterScope.resolve(owned.owned_root, owned.mission_dir)` unchanged; add no hardcoded worktree paths or broader runtime-signature changes. | Technical | High | Open |
| C-003 | Narrow umbrella slice | Exclude the CLI startup-budget failure, #7206, unrelated recovered nightly failures, and nearby PRs #7273/#7287. Reference #6788 without claiming the umbrella issue is fully resolved. | Business | High | Open |
| C-004 | Honest nightly verdict | Do not claim main is recovered until the relevant nightly performance suite runs green on the merged commit. | Business | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The new canonical-status prompt integration case fails before the production change with `MISSION_CONTEXT_CONFLICT` and passes afterward, with foreign-path refusal passing in the same file. — [build] · no-op passable: no
- **SC-002**: Installed-CLI parameter `[0]` changes from one red reproduction to one pass; both focused owned integration files pass with zero failures. — [build] · no-op passable: no
- **SC-003**: The draft PR and issue evidence explicitly mark all 20 parameters and umbrella recovery as pending merged-commit nightly verification, with no main-recovery claim and no startup-budget scope claim. — [build] · no-op passable: no

## Assumptions

- Current `origin/main` and every open PR file list were checked on 2026-11-07; no open PR changes the owned charter guard or its focused integration/e2e tests.
- The research evidence is a lead, not acceptance proof; red-first evidence is reconfirmed through the current test entry point before editing production code.
